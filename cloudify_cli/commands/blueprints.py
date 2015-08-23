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

"""
Handles all commands that start with 'cfy blueprints'
"""

import os
import urlparse

from cloudify_cli import utils
from cloudify_cli.logger import get_logger
from cloudify_cli import messages
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.utils import print_table
from dsl_parser.parser import parse_from_path
from dsl_parser.exceptions import DSLParsingException

SUPPORTED_ARCHIVE_TYPES = ['zip', 'tar', 'tar.gz', 'tar.bz2']


def validate(blueprint_path):
    logger = get_logger()

    logger.info(
        messages.VALIDATING_BLUEPRINT.format(blueprint_path.name))
    try:
        resolver = utils.get_import_resolver()
        parse_from_path(dsl_file_path=blueprint_path.name, resolver=resolver)
    except DSLParsingException as ex:
        msg = (messages.VALIDATING_BLUEPRINT_FAILED
               .format(blueprint_path.name, str(ex)))
        raise CloudifyCliError(msg)
    logger.info(messages.VALIDATING_BLUEPRINT_SUCCEEDED)


def upload(blueprint_path, blueprint_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    validate(blueprint_path)

    logger.info('Uploading blueprint {0} to management server {1}'
                .format(blueprint_path.name, management_ip))
    client = utils.get_rest_client(management_ip)
    blueprint = client.blueprints.upload(blueprint_path.name, blueprint_id)
    logger.info("Uploaded blueprint, blueprint's id is: {0}"
                .format(blueprint.id))


def publish_archive(archive_location, blueprint_filename, blueprint_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()

    for archive_type in SUPPORTED_ARCHIVE_TYPES:
        if archive_location.endswith('.{0}'.format(archive_type)):
            break
    else:
        raise CloudifyCliError(
            "Can't publish archive {0} - it's of an unsupported archive type. "
            "Supported archive types: {1}".format(archive_location,
                                                  SUPPORTED_ARCHIVE_TYPES))

    archive_location_type = 'URL'
    if not urlparse.urlparse(archive_location).scheme:
        # archive_location is not a URL - validate it's a file path
        if not os.path.isfile(archive_location):
            raise CloudifyCliError(
                "Can't publish archive {0} - it's not a valid URL nor a path "
                "to an archive file".format(archive_location))
        archive_location_type = 'path'
        archive_location = os.path.expanduser(archive_location)

    logger.info('Publishing blueprint archive from {0} {1} to management '
                'server {2}'
                .format(archive_location_type,
                        archive_location,
                        management_ip))

    client = utils.get_rest_client(management_ip)
    blueprint = client.blueprints.publish_archive(
        archive_location, blueprint_id, blueprint_filename)
    logger.info("Published blueprint archive, blueprint's id is: {0}"
                .format(blueprint.id))


def download(blueprint_id, output):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info(messages.DOWNLOADING_BLUEPRINT.format(blueprint_id))
    client = utils.get_rest_client(management_ip)
    target_file = client.blueprints.download(blueprint_id, output)
    logger.info(messages.DOWNLOADING_BLUEPRINT_SUCCEEDED
                .format(blueprint_id, target_file))


def delete(blueprint_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info('Deleting blueprint {0} from management server {1}'
                .format(blueprint_id, management_ip))
    client = utils.get_rest_client(management_ip)
    client.blueprints.delete(blueprint_id)
    logger.info('Deleted blueprint successfully')


def ls():
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)
    logger.info('Getting blueprints list... [manager={0}]'
                .format(management_ip))

    pt = utils.table(['id', 'created_at', 'updated_at'],
                     data=client.blueprints.list())

    print_table('Blueprints:', pt)
