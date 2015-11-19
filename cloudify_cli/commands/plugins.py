########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
Handles all commands that start with 'cfy plugins'
"""
import tarfile

from cloudify_cli import utils
from cloudify_cli import messages
from cloudify_cli.logger import get_logger
from cloudify_cli.utils import print_table
from cloudify_cli.exceptions import CloudifyCliError


def validate(plugin_path):
    logger = get_logger()

    logger.info(
        messages.VALIDATING_PLUGIN.format(plugin_path.name))
    if not tarfile.is_tarfile(plugin_path.name):
        raise CloudifyCliError('Archive {0} is of an unsupported archive type.'
                               ' Only tar.gz is allowed'
                               .format(plugin_path.name))
    with tarfile.open(plugin_path.name, 'r') as tar:
        tar_members = tar.getmembers()
        package_json_path = '{0}/package.json'.format(tar_members[0].name)
        try:
            package_member = tar.getmember(package_json_path)
        except KeyError:
            raise CloudifyCliError(messages.VALIDATING_PLUGIN_FAILED
                                   .format(plugin_path, 'package.json was not '
                                                        'found in archive'))
        try:
            tar.extractfile(package_member).read()
        except:
            raise CloudifyCliError(messages.VALIDATING_PLUGIN_FAILED
                                   .format(plugin_path, 'unable to read '
                                                        'package.json'))

    logger.info(messages.VALIDATING_PLUGIN_SUCCEEDED)


def delete(plugin_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info(messages.PLUGIN_DELETE.format(plugin_id, management_ip))
    client.plugins.delete(plugin_id)

    logger.info(messages.PLUGIN_DELETE_SUCCEEDED.format(plugin_id))


def upload(plugin_path):
    server_ip = utils.get_management_server_ip()
    utils.upload_plugin(plugin_path, server_ip,
                        utils.get_rest_client(server_ip), validate)


def download(plugin_id,
             output):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info(messages.DOWNLOADING_PLUGIN.format(plugin_id))
    client = utils.get_rest_client(management_ip)
    target_file = client.plugins.download(plugin_id, output)
    logger.info(messages.DOWNLOADING_PLUGIN_SUCCEEDED.format(plugin_id,
                                                             target_file))


fields = ['id', 'package_name', 'package_version', 'supported_platform',
          'distribution', 'distribution_release', 'uploaded_at']


def get(plugin_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info(messages.PLUGINS_GET.format(plugin_id, management_ip))
    plugin = client.plugins.get(plugin_id, _include=fields)

    pt = utils.table(fields, data=[plugin])
    print_table('Plugin:', pt)


def ls():
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info(messages.PLUGINS_LIST.format(management_ip))
    plugins = client.plugins.list(_include=fields)

    pt = utils.table(fields, data=plugins)
    print_table('Plugins:', pt)
