########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import sys
import json
import shutil
import tempfile

import click

from cloudify.utils import LocalCommandRunner
from dsl_parser.parser import parse_from_path
from dsl_parser import constants as dsl_constants
from dsl_parser.exceptions import DSLParsingException

from .. import env
from .. import utils
from .. import table
from .. import exceptions
from ..config import cfy
from ..exceptions import CloudifyCliError
from ..constants import DEFAULT_BLUEPRINT_PATH


SUPPORTED_ARCHIVE_TYPES = ('zip', 'tar', 'tar.gz', 'tar.bz2')
DESCRIPTION_LIMIT = 20


@cfy.group(name='blueprints')
@cfy.options.verbose()
def blueprints():
    """Handle blueprints on the manager
    """
    pass


@blueprints.command(name='validate',
                    short_help='Validate a blueprint')
@cfy.argument('blueprint-path')
@cfy.options.verbose()
@cfy.pass_logger
def validate_blueprint(blueprint_path, logger):
    """Validate a blueprint

    `BLUEPRINT_PATH` is the path of the blueprint to validate.
    """
    logger.info('Validating blueprint: {0}'.format(blueprint_path))
    try:
        resolver = env.get_import_resolver()
        validate_version = env.is_validate_definitions_version()
        parse_from_path(
            dsl_file_path=blueprint_path,
            resolver=resolver,
            validate_version=validate_version)
    except DSLParsingException as ex:
        raise CloudifyCliError('Failed to validate blueprint {0}'.format(ex))
    logger.info('Blueprint validated successfully')


@blueprints.command(name='upload',
                    short_help='Upload a blueprint [manager only]')
@cfy.argument('blueprint-path')
@cfy.options.blueprint_id()
@cfy.options.blueprint_filename()
@cfy.options.validate
@cfy.options.verbose()
@cfy.assert_manager_active
@cfy.pass_client()
@cfy.pass_logger
@click.pass_context
def upload(ctx,
           blueprint_path,
           blueprint_id,
           blueprint_filename,
           validate,
           logger,
           client):
    """Upload a blueprint to the manager

    `BLUEPRINT_PATH` can be either a local blueprint yaml file or
    blueprint archive; a url to a blueprint archive or an
    `organization/blueprint_repo[:tag/branch]` (to be
    retrieved from GitHub)
    """
    processed_blueprint_path = get_blueprint(
        blueprint_path, blueprint_filename)

    try:
        if validate:
            ctx.invoke(
                validate_blueprint,
                blueprint_path=processed_blueprint_path)
        blueprint_id = blueprint_id or get_blueprint_id(
            processed_blueprint_path, blueprint_filename)

        progress_handler = utils.generate_progress_handler(blueprint_path, '')
        logger.info('Uploading blueprint {0}...'.format(blueprint_path))
        blueprint = client.blueprints.upload(processed_blueprint_path,
                                             blueprint_id,
                                             progress_handler)
        logger.info("Blueprint uploaded. The blueprint's id is {0}".format(
            blueprint.id))
    finally:
        # Every situation other than the user providing a path of a local
        # yaml means a temp folder will be created that should be later
        # removed.
        if processed_blueprint_path != blueprint_path:
            shutil.rmtree(os.path.dirname(os.path.dirname(
                processed_blueprint_path)))


@blueprints.command(name='download',
                    short_help='Download a blueprint [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.output_path
@cfy.options.verbose()
@cfy.assert_manager_active
@cfy.pass_client()
@cfy.pass_logger
def download(blueprint_id, output_path, logger, client):
    """Download a blueprint from the manager

    `BLUEPRINT_ID` is the id of the blueprint to download.
    """
    logger.info('Downloading blueprint {0}...'.format(blueprint_id))
    blueprint_name = output_path if output_path else blueprint_id
    progress_handler = utils.generate_progress_handler(blueprint_name, '')
    target_file = client.blueprints.download(blueprint_id,
                                             output_path,
                                             progress_handler)
    logger.info('Blueprint downloaded as {0}'.format(target_file))


@blueprints.command(name='delete',
                    short_help='Delete a blueprint [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.verbose()
@cfy.assert_manager_active
@cfy.pass_client()
@cfy.pass_logger
def delete(blueprint_id, logger, client):
    """Delete a blueprint from the manager
    """
    logger.info('Deleting blueprint {0}...'.format(blueprint_id))
    client.blueprints.delete(blueprint_id)
    logger.info('Blueprint deleted')


@blueprints.command(name='list',
                    short_help='List blueprints [manager only]')
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.verbose()
@cfy.assert_manager_active
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by, descending, logger, client):
    """List all blueprints
    """
    def trim_description(blueprint):
        if blueprint['description'] is not None:
            if len(blueprint['description']) >= DESCRIPTION_LIMIT:
                blueprint['description'] = '{0}..'.format(
                    blueprint['description'][:DESCRIPTION_LIMIT - 2])
        else:
            blueprint['description'] = ''
        return blueprint

    logger.info('Listing all blueprints...')
    blueprints = [trim_description(b) for b in client.blueprints.list(
        sort=sort_by, is_descending=descending)]

    columns = [
        'id', 'description', 'main_file_name', 'created_at', 'updated_at']
    pt = table.generate(columns, data=blueprints)
    table.log('Blueprints:', pt)


@blueprints.command(name='get',
                    short_help='Retrieve blueprint information [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.verbose()
@cfy.assert_manager_active
@cfy.pass_client()
@cfy.pass_logger
def get(blueprint_id, logger, client):
    """Retrieve information for a specific blueprint

    `BLUEPRINT_ID` is the id of the blueprint to get information on.
    """
    logger.info('Retrieving blueprint {0}...'.format(blueprint_id))
    blueprint = client.blueprints.get(blueprint_id)
    deployments = client.deployments.list(_include=['id'],
                                          blueprint_id=blueprint_id)
    blueprint['#deployments'] = len(deployments)

    columns = \
        ['id', 'main_file_name', 'created_at', 'updated_at', '#deployments']
    pt = table.generate(columns, data=[blueprint])
    pt.max_width = 50
    table.log('Blueprint:', pt)

    logger.info('Description:')
    logger.info('{0}\n'.format(blueprint['description'] or ''))

    logger.info('Existing deployments:')
    logger.info('{0}\n'.format(json.dumps([d['id'] for d in deployments])))


@blueprints.command(name='inputs',
                    short_help='Retrieve blueprint inputs [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.verbose()
@cfy.assert_manager_active
@cfy.pass_client()
@cfy.pass_logger
def inputs(blueprint_id, logger, client):
    """Retrieve inputs for a specific blueprint

    `BLUEPRINT_ID` is the path of the blueprint to get inputs for.
    """
    logger.info('Retrieving inputs for blueprint {0}...'.format(blueprint_id))
    blueprint = client.blueprints.get(blueprint_id)
    inputs = blueprint['plan']['inputs']
    data = [{'name': name,
             'type': input.get('type', '-'),
             'default': input.get('default', '-'),
             'description': input.get('description', '-')}
            for name, input in inputs.iteritems()]

    columns = ['name', 'type', 'default', 'description']
    pt = table.generate(columns, data=data)
    table.log('Inputs:', pt)


@blueprints.command(name='package',
                    short_help='Create a blueprint archive')
@cfy.argument('blueprint-path')
@cfy.options.optional_output_path
@cfy.options.validate
@cfy.options.verbose()
@cfy.pass_logger
@click.pass_context
def package(ctx, blueprint_path, output_path, validate, logger):
    """Create a blueprint archive

    `BLUEPRINT_PATH` is either the path to the blueprint yaml itself or
    to the directory in which the blueprint yaml files resides.
    """
    blueprint_path = os.path.abspath(blueprint_path)
    destination = output_path or get_blueprint_id(blueprint_path)

    if validate:
        ctx.invoke(validate_blueprint, blueprint_path=blueprint_path)
    logger.info('Creating blueprint archive {0}...'.format(destination))
    if os.path.isdir(blueprint_path):
        path_to_package = blueprint_path
    elif os.path.isfile(blueprint_path):
        path_to_package = os.path.dirname(blueprint_path)
    else:
        raise CloudifyCliError(
            "You must provide a path to a blueprint's directory or to a "
            "blueprint yaml file residing in a blueprint's directory.")
    if os.name == 'nt':
        utils.zip(path_to_package, destination + '.zip')
    else:
        utils.tar(path_to_package, destination + '.tar.gz')
    logger.info('Packaging complete!')


@blueprints.command(name='create-requirements',
                    short_help='Create pip-requirements')
@cfy.argument('blueprint-path', type=click.Path(exists=True))
@cfy.options.optional_output_path
@cfy.options.verbose()
@cfy.pass_logger
def create_requirements(blueprint_path, output_path, logger):
    """Generate a pip-compliant requirements file for a given blueprint

    `BLUEPRINT_PATH` is the path to the blueprint for which the file
    will be generated.
    """
    if output_path and os.path.exists(output_path):
        raise exceptions.CloudifyCliError(
            'Path {0} already exists'.format(output_path))

    requirements = _create_requirements(blueprint_path=blueprint_path)

    if output_path:
        utils.dump_to_file(requirements, output_path)
        logger.info('Requirements file created successfully --> {0}'
                    .format(output_path))
    else:
        for requirement in requirements:
            logger.info(requirement)


@blueprints.command(name='install-plugins',
                    short_help='Install plugins locally [locally]')
@cfy.argument('blueprint-path', type=click.Path(exists=True))
@cfy.options.verbose()
@cfy.assert_local_active
@cfy.pass_logger
def install_plugins(blueprint_path, logger):
    """Install the necessary plugins for a given blueprint in the
    local environment.

    Currently only supports passing the YAML of the blueprint directly.

    `BLUEPRINT_PATH` is the path to the blueprint to install plugins for.
    """
    logger.info('Installing plugins...')
    requirements = _create_requirements(blueprint_path=blueprint_path)

    if requirements:
        # Validate we are inside a virtual env
        if not utils.is_virtual_env():
            raise exceptions.CloudifyCliError(
                'You must be running inside a '
                'virtualenv to install blueprint plugins')

        runner = LocalCommandRunner(logger)
        # Dump the requirements to a file and let pip install it.
        # This will utilize pip's mechanism of cleanup in case an installation
        # fails.
        tmp_path = tempfile.mkstemp(suffix='.txt', prefix='requirements_')[1]
        utils.dump_to_file(collection=requirements, file_path=tmp_path)
        command_parts = [sys.executable, '-m', 'pip', 'install', '-r',
                         tmp_path]
        runner.run(command=' '.join(command_parts), stdout_pipe=False)
    else:
        logger.info('There are no plugins to install')


def _create_requirements(blueprint_path):

    parsed_dsl = parse_from_path(dsl_file_path=blueprint_path)

    requirements = _plugins_to_requirements(
        blueprint_path=blueprint_path,
        plugins=parsed_dsl[dsl_constants.DEPLOYMENT_PLUGINS_TO_INSTALL])

    for node in parsed_dsl['nodes']:
        requirements.update(_plugins_to_requirements(
            blueprint_path=blueprint_path,
            plugins=node['plugins']))
    return requirements


def _plugins_to_requirements(blueprint_path, plugins):

    sources = set()
    for plugin in plugins:
        if plugin[dsl_constants.PLUGIN_INSTALL_KEY]:
            source = plugin[dsl_constants.PLUGIN_SOURCE_KEY]
            if not source:
                continue
            if '://' in source:
                # URL
                sources.add(source)
            else:
                # Local plugin (should reside under the 'plugins' dir)
                plugin_path = os.path.join(
                    os.path.abspath(os.path.dirname(blueprint_path)),
                    'plugins',
                    source)
                sources.add(plugin_path)
    return sources


def get_blueprint(source, blueprint_filename='blueprint.yaml'):
    """Get a source and return a directory containing the blueprint

    if it's a URL of an archive, download and extract it.
    if it's a local archive, extract it.
    if it's a local yaml, return it.
    else turn to github and try to get it.
    else should implicitly fail.
    """
    def get_blueprint_file(final_source):
        archive_root = utils.extract_archive(final_source)
        blueprint = os.path.join(archive_root, os.listdir(archive_root)[0])
        blueprint_file = os.path.join(blueprint, blueprint_filename)
        if not os.path.isfile(blueprint_file):
            raise CloudifyCliError(
                'Could not find `{0}`. Please provide the name of the main '
                'blueprint file by using the `-n/--blueprint-filename` flag'
                .format(blueprint_filename))
        return blueprint_file

    if '://' in source:
        downloaded_source = utils.download_file(source)
        return get_blueprint_file(downloaded_source)
    elif os.path.isfile(source):
        if utils.is_archive(source):
            return get_blueprint_file(source)
        else:
            # Maybe check if yaml. If not, verified by dsl parser
            return source
    elif len(source.split('/')) == 2:
        downloaded_source = _get_from_github(source)
        # GitHub archives provide an inner folder with each archive.
        return get_blueprint_file(downloaded_source)
    else:
        raise CloudifyCliError(
            'You must provide either a path to a local file, a remote URL '
            'or a GitHub `organization/repository[:tag/branch]`')


def _get_from_github(source):
    """Returns a path to a downloaded github archive.

    Source to download should be in the format of `org/repo[:tag/branch]`.
    """
    source_parts = source.split(':', 1)
    repo = source_parts[0]
    tag = source_parts[1] if len(source_parts) == 2 else 'master'
    url = 'https://github.com/{0}/archive/{1}.tar.gz'.format(repo, tag)
    return utils.download_file(url)


def get_blueprint_id(blueprint_folder,
                     blueprint_filename=DEFAULT_BLUEPRINT_PATH):
    """The name of the blueprint will be the name of the folder.
    If blueprint_filename is provided, it will be appended to the
    folder.
    """
    blueprint_id = os.path.dirname(blueprint_folder).split('/')[-1]
    if not blueprint_filename == DEFAULT_BLUEPRINT_PATH:
        filename, _ = os.path.splitext(os.path.basename(blueprint_filename))
        blueprint_id = (blueprint_id + '.' + filename)
    return blueprint_id.replace('_', '-')
