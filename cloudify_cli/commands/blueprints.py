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
import json
import shutil

import click

from dsl_parser.parser import parse_from_path
from dsl_parser.exceptions import DSLParsingException

from .. import env
from .. import utils
from .. import common
from ..config import cfy
from ..logger import get_logger
from ..exceptions import CloudifyCliError


# TODO: We currently only support zip and tar.gz.
# We need to add tar and tar.gz2 back.
SUPPORTED_ARCHIVE_TYPES = ('zip', 'tar', 'tar.gz', 'tar.bz2')
DESCRIPTION_LIMIT = 20


@cfy.group(name='blueprints')
@cfy.options.verbose
def blueprints():
    """Handle blueprints on the manager
    """
    pass


@blueprints.command(name='validate')
@cfy.argument('blueprint-path')
@cfy.options.verbose
def validate_blueprint(blueprint_path):
    """Validate a blueprint

    `BLUEPRINT_PATH` is the path of the blueprint to validate.
    """
    logger = get_logger()

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


@blueprints.command(name='upload')
@cfy.argument('blueprint-path')
@cfy.options.blueprint_id()
@cfy.options.blueprint_filename()
@cfy.options.validate
@cfy.options.verbose
@click.pass_context
def upload(ctx,
           blueprint_path,
           blueprint_id,
           blueprint_filename,
           validate):
    """Upload a blueprint to the manager

    `BLUEPRINT_PATH` can be either a local blueprint yaml file or
    blueprint archive; a url to a blueprint archive or an
    `organization/blueprint_repo[:tag/branch]` (to be
    retrieved from GitHub)
    """
    env.assert_manager_active()

    logger = get_logger()
    client = env.get_rest_client()

    # TODO: Consider using client.blueprints.publish_archive if the
    # path is an archive. This requires additional logic when identifying
    # the source.
    # TODO: If not providing an archive, but a path to a local yaml,
    # blueprint_filename is only relevant for the naming of the blueprint
    # and not for the actual location. This is.. weird behavior.
    processed_blueprint_path = common.get_blueprint(
        blueprint_path, blueprint_filename)

    try:
        if validate:
            ctx.invoke(
                validate_blueprint,
                blueprint_path=processed_blueprint_path)
        blueprint_id = blueprint_id or common.set_blueprint_id(
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


@blueprints.command(name='download')
@cfy.argument('blueprint-id')
@cfy.options.output_path
@cfy.options.verbose
def download(blueprint_id, output_path):
    """Download a blueprint from the manager

    `BLUEPRINT_ID` is the id of the blueprint to download.
    """
    env.assert_manager_active()

    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Downloading blueprint {0}...'.format(blueprint_id))
    blueprint_name = output_path if output_path else blueprint_id
    progress_handler = utils.generate_progress_handler(blueprint_name, '')
    target_file = client.blueprints.download(blueprint_id,
                                             output_path,
                                             progress_handler)
    logger.info('Blueprint downloaded as {0}'.format(target_file))


@blueprints.command(name='delete')
@cfy.argument('blueprint-id')
@cfy.options.verbose
def delete(blueprint_id):
    """Delete a blueprint from the manager
    """
    env.assert_manager_active()

    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Deleting blueprint {0}...'.format(blueprint_id))
    client.blueprints.delete(blueprint_id)
    logger.info('Blueprint deleted')


@blueprints.command(name='list')
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.verbose
def list(sort_by=None, descending=False):
    """List all blueprints
    """
    env.assert_manager_active()

    logger = get_logger()
    client = env.get_rest_client()

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

    pt = utils.table(['id', 'description', 'main_file_name',
                      'created_at', 'updated_at'],
                     data=blueprints)

    common.print_table('Available blueprints:', pt)


@blueprints.command(name='get')
@cfy.argument('blueprint-id')
@cfy.options.verbose
def get(blueprint_id):
    """Retrieve information for a specific blueprint

    `BLUEPRINT_ID` is the id of the blueprint to get information on.
    """
    env.assert_manager_active()

    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Retrieving blueprint {0}...'.format(blueprint_id))
    blueprint = client.blueprints.get(blueprint_id)
    deployments = client.deployments.list(_include=['id'],
                                          blueprint_id=blueprint_id)
    blueprint['#deployments'] = len(deployments)

    pt = utils.table(['id', 'main_file_name', 'created_at', 'updated_at',
                      '#deployments'], [blueprint])
    pt.max_width = 50
    common.print_table('Blueprint:', pt)

    logger.info('Description:')
    logger.info('{0}\n'.format(blueprint['description'] or ''))

    logger.info('Existing deployments:')
    logger.info('{0}\n'.format(json.dumps([d['id'] for d in deployments])))


@blueprints.command(name='inputs')
@cfy.argument('blueprint-id')
@cfy.options.verbose
def inputs(blueprint_id):
    """Retrieve inputs for a specific blueprint

    `BLUEPRINT_ID` is the path of the blueprint to get inputs for.
    """
    env.assert_manager_active()

    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Retrieving inputs for blueprint {0}...'.format(blueprint_id))
    blueprint = client.blueprints.get(blueprint_id)
    inputs = blueprint['plan']['inputs']
    data = [{'name': name,
             'type': input.get('type', '-'),
             'default': input.get('default', '-'),
             'description': input.get('description', '-')}
            for name, input in inputs.iteritems()]

    pt = utils.table(['name', 'type', 'default', 'description'],
                     data=data)

    common.print_table('Inputs:', pt)


@blueprints.command(name='package')
@cfy.argument('blueprint-path')
@cfy.options.optional_output_path
@cfy.options.validate
@cfy.options.verbose
@click.pass_context
def package(ctx, blueprint_path, output_path, validate):
    """Create a blueprint archive

    `BLUEPRINT_PATH` is either the path to the blueprint yaml itself or
    to the directory in which the blueprint yaml files resides.
    """
    logger = get_logger()

    blueprint_path = os.path.abspath(blueprint_path)
    # TODO: Should we add blueprint_filename here?
    destination = output_path or common.set_blueprint_id(blueprint_path)

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
