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
import urlparse

import click

from dsl_parser.parser import parse_from_path
from dsl_parser.exceptions import DSLParsingException

from .. import env
from .. import utils
from .. import common
from ..config import cfy
from ..logger import get_logger
from ..exceptions import CloudifyCliError


SUPPORTED_ARCHIVE_TYPES = ('zip', 'tar', 'tar.gz', 'tar.bz2')
DESCRIPTION_LIMIT = 20


@cfy.group(name='blueprints')
@cfy.options.verbose
def blueprints():
    """Handle blueprints on the manager
    """
    env.assert_manager_active()


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
        resolver = utils.get_import_resolver()
        validate_version = utils.is_validate_definitions_version()
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

    `BLUEPRINT_PATH` is the path of the blueprint to upload.

    This can be either a path to a local yaml, a URL of a blueprint archive
    or a path to a local blueprint archive.
    """

    # TODO: Replace this entire crazy contraption with common.get_blueprint.
    if _is_archive(blueprint_path):
        # TODO: allow to upload from github like so:
        # `cfy blueprints upload cloudify-examples/my-blueprint:branch`
        blueprint_id = blueprint_id or utils.generate_suffixed_id(
            get_archive_id(blueprint_path))
        if not blueprint_filename:
            raise CloudifyCliError(
                'Supplying an archive requires that the name of the main '
                'blueprint yaml file in the archive be provided via the '
                '`--blueprint-filename` flag. (e.g. blueprint.yaml)')
        if validate:
            raise CloudifyCliError(
                'The `--validate` flag is only relevant when uploading '
                'from a file.')
        _publish_archive(
            blueprint_path,
            blueprint_filename,
            blueprint_id)
    elif os.path.isfile(blueprint_path):
        filename, _ = os.path.splitext(
            os.path.basename(blueprint_path))
        blueprint_id = blueprint_id or utils.generate_suffixed_id(
            os.path.basename(filename))
        _publish_directory(
            ctx,
            blueprint_path,
            blueprint_id,
            validate)
    else:
        raise CloudifyCliError(
            'You must either provide a path to a local blueprint file, '
            'a path to a blueprint archive or a URL of a blueprint archive. '
            'Archive can be of types: {0}'.format(SUPPORTED_ARCHIVE_TYPES))


def _publish_directory(ctx, blueprint_path, blueprint_id, validate):
    logger = get_logger()
    client = env.get_rest_client()

    if validate:
        ctx.invoke(validate_blueprint, blueprint_path=blueprint_path)
    else:
        logger.debug("Skipping blueprint validation...")
    logger.info('Uploading blueprint {0}...'.format(blueprint_path))

    blueprint = client.blueprints.upload(blueprint_path, blueprint_id)
    logger.info("Blueprint uploaded. "
                "The blueprint's id is {0}".format(blueprint.id))


def _publish_archive(archive_location, blueprint_filename, blueprint_id):
    logger = get_logger()
    client = env.get_rest_client()

    if not _is_archive(archive_location):
        raise CloudifyCliError(
            "Can't publish archive {0} - it's of an unsupported "
            "archive type. Supported archive types: {1}".format(
                archive_location, SUPPORTED_ARCHIVE_TYPES))

    archive_location, archive_location_type = \
        determine_archive_type(archive_location)

    logger.info('Publishing blueprint archive from {0} {1}...'.format(
        archive_location_type, archive_location))

    blueprint = client.blueprints.publish_archive(
        archive_location, blueprint_id, blueprint_filename)
    logger.info("Blueprint archive published. "
                "The blueprint's id is {0}".format(blueprint.id))


def _is_archive(archive_location):
    # TODO: actually check the format of the files instead of their extensions.
    # We can use `zipfile.is_zipfile` and `tarfile.is_tarfile` for example.
    return archive_location.endswith(SUPPORTED_ARCHIVE_TYPES)


def determine_archive_type(archive_location):

    if not urlparse.urlparse(archive_location).scheme:
        # archive_location is not a URL - validate it's a file path
        archive_location = os.path.expanduser(archive_location)
        if not os.path.isfile(archive_location):
            raise CloudifyCliError(
                "Can't publish archive {0} - "
                "it's not a valid URL nor a path to a valid archive".format(
                    archive_location))
        # The archive exists locally. Return it, and inform it's a path
        return archive_location, 'path'

    # The archive is a url. Return it, and inform it's a url
    return os.path.expanduser(archive_location), 'url'


@blueprints.command(name='download')
@cfy.argument('blueprint-id')
@cfy.options.output_path
@cfy.options.verbose
def download(blueprint_id, output_path):
    """Download a blueprint from the manager

    `BLUEPRINT_ID` is the id of the blueprint to download.
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Downloading blueprint {0}...'.format(blueprint_id))
    target_file = client.blueprints.download(blueprint_id, output_path)

    logger.info('Blueprint downloaded as {0}'.format(target_file))


@blueprints.command(name='delete')
@cfy.argument('blueprint-id')
@cfy.options.verbose
def delete(blueprint_id):
    """Delete a blueprint from the manager
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Deleting blueprint {0}...'.format(blueprint_id))
    client.blueprints.delete(blueprint_id)
    logger.info('Blueprint deleted')


@blueprints.command(name='list')
@cfy.options.verbose
def list():
    """List all blueprints
    """
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
    blueprints = [trim_description(b) for b in client.blueprints.list()]

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
    logger.info('{0}\n'.format(blueprint['description'] if
                               blueprint['description'] is not None else ''))

    logger.info('Existing deployments:')
    logger.info('{0}\n'.format(json.dumps([d['id'] for d in deployments])))


@blueprints.command(name='inputs')
@cfy.argument('blueprint-id')
@cfy.options.verbose
def inputs(blueprint_id):
    """Retrieve inputs for a specific blueprint

    `BLUEPRINT_ID` is the path of the blueprint to get inputs for.
    """
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


# TODO: move to utils
def get_archive_id(archive_location):
    (archive_location, archive_location_type) = \
        determine_archive_type(archive_location)
    # if the archive is a local path, assign blueprint_id the name of
    # the archive file without the extension
    if archive_location_type == 'path':
        filename, _ = os.path.splitext(
            os.path.basename(archive_location))
        return filename
    # if the archive is a url, assign blueprint_id same of the file
    # that the url leads to, without the extension.
    # e.g. http://example.com/path/archive.zip?para=val#sect -> archive
    elif archive_location_type == 'url':
        path = urlparse.urlparse(archive_location).path
        archive_file = path.split('/')[-1]
        archive_name = archive_file.split('.')[0]
        return archive_name
    else:
        raise CloudifyCliError("The archive's source is not a local "
                               "file path nor a web url")
