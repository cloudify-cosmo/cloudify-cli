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

from .. import utils
from ..config import options
from .validate import validate
from ..config import helptexts
from ..logger import get_logger
from ..exceptions import CloudifyCliError

SUPPORTED_ARCHIVE_TYPES = ('zip', 'tar', 'tar.gz', 'tar.bz2')
DESCRIPTION_LIMIT = 20


@click.group(context_settings=utils.CLICK_CONTEXT_SETTINGS)
def blueprints():
    """Handle blueprints on the manager
    """
    pass


@blueprints.command(name='validate')
@click.argument('blueprint-path', required=True)
def validate_blueprint(blueprint_path):
    """Validate a blueprint
    """
    validate(blueprint_path)


@blueprints.command(name='upload')
@click.argument('blueprint-path', required=True)
@click.option('-b',
              '--blueprint-id',
              help=helptexts.BLUEPRINT_ID)
@options.blueprint_filename()
@click.option('--validate',
              is_flag=True,
              help=helptexts.VALIDATE_BLUEPRINT)
def upload_blueprint(blueprint_path,
                     blueprint_id,
                     blueprint_filename,
                     validate):
    """Upload a blueprint to the manager
    """
    upload(blueprint_path,
           blueprint_id,
           blueprint_filename,
           validate)


def upload(blueprint_path,
           blueprint_id,
           blueprint_filename,
           validate):
    # TODO: to fix the ambiguity of whether this is an archive
    # or not, we can allow the user to pass an `archive_format`
    # parameter which states that the user (explicitly) wanted
    # to pass a path to an archive.
    blueprint_id = blueprint_id or utils._generate_suffixed_id(
        get_archive_id(blueprint_path))

    if not _is_archive(blueprint_path):
        _publish_directory(
            blueprint_path,
            blueprint_id,
            validate)
    else:
        if validate:
            raise CloudifyCliError(
                'Validate is only relevant when uploading from a file.')
        _publish_archive(
            blueprint_path,
            blueprint_filename,
            blueprint_id)


def _publish_directory(blueprint_path, blueprint_id, validate):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    if validate:
        validate_blueprint(blueprint_path)
    else:
        logger.debug("Skipping blueprint validation...")

    logger.info('Uploading blueprint {0}...'.format(blueprint_path))
    client = utils.get_rest_client(management_ip)
    blueprint = client.blueprints.upload(blueprint_path, blueprint_id)
    logger.info("Blueprint uploaded. "
                "The blueprint's id is {0}".format(blueprint.id))


def _publish_archive(archive_location, blueprint_filename, blueprint_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()

    check_if_archive_type_is_supported(archive_location)

    archive_location, archive_location_type = \
        determine_archive_type(archive_location)

    logger.info('Publishing blueprint archive from {0} {1}...'.format(
        archive_location_type, archive_location))

    client = utils.get_rest_client(management_ip)
    blueprint = client.blueprints.publish_archive(
        archive_location, blueprint_id, blueprint_filename)
    logger.info("Blueprint archive published. "
                "The blueprint's id is {0}".format(blueprint.id))


def _is_archive(archive_location):
    return archive_location.endswith(SUPPORTED_ARCHIVE_TYPES)


def check_if_archive_type_is_supported(archive_location):
    if not _is_archive(archive_location):
        raise CloudifyCliError(
            "Can't publish archive {0} - it's of an unsupported "
            "archive type. Supported archive types: {1}".format(
                archive_location, SUPPORTED_ARCHIVE_TYPES))


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
@click.argument('blueprint-id', required=True)
@options.output_path
def download(blueprint_id, output_path):
    """Download a blueprint from the manager
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info('Downloading blueprint {0}...'.format(blueprint_id))
    target_file = client.blueprints.download(blueprint_id, output_path)

    logger.info('Blueprint downloaded as {0}'.format(target_file))


@blueprints.command(name='delete')
@click.argument('blueprint-id', required=True)
def delete(blueprint_id):
    """Delete a blueprint from the manager
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info('Deleting blueprint {0}...'.format(blueprint_id))
    client.blueprints.delete(blueprint_id)

    logger.info('Blueprint deleted')


@blueprints.command(name='ls')
def ls():
    """List all blueprints
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

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

    utils.print_table('Available blueprints:', pt)


@blueprints.command(name='get')
@click.argument('blueprint-id', required=True)
def get(blueprint_id):
    """Retrieve information for a specific blueprint
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info('Retrieving blueprint {0}...'.format(blueprint_id))
    blueprint = client.blueprints.get(blueprint_id)

    deployments = client.deployments.list(_include=['id'],
                                          blueprint_id=blueprint_id)
    blueprint['#deployments'] = len(deployments)

    pt = utils.table(['id', 'main_file_name', 'created_at', 'updated_at',
                      '#deployments'], [blueprint])
    pt.max_width = 50
    utils.print_table('Blueprint:', pt)

    logger.info('Description:')
    logger.info('{0}\n'.format(blueprint['description'] if
                               blueprint['description'] is not None else ''))

    logger.info('Existing deployments:')
    logger.info('{0}\n'.format(json.dumps([d['id'] for d in deployments])))


@blueprints.command(name='inputs')
@click.argument('blueprint-id', required=True)
def inputs(blueprint_id):
    """Retrieve inputs for a specific blueprint
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

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

    utils.print_table('Inputs:', pt)


# TODO: move to utils
def get_archive_id(archive_location):
    (archive_location, archive_location_type) = \
        determine_archive_type(archive_location)
    # if the archive is a local path, assign blueprint_id the name of
    # the archive file without the extension
    if archive_location_type == 'path':
        filename, ext = os.path.splitext(
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
