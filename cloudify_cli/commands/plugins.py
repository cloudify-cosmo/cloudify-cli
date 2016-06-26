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

import click

from cloudify_cli import utils
from cloudify_cli.config import helptexts
from cloudify_cli.logger import get_logger
from cloudify_cli.utils import print_table
from cloudify_cli.exceptions import CloudifyCliError


@click.group(name='plugins', context_settings=utils.CLICK_CONTEXT_SETTINGS)
def plugins():
    """Handle plugins on the manager
    """
    pass


@plugins.command(name='validate')
@click.argument('plugin-path', required=True)
def validate(plugin_path):
    """Validate a plugin

    This will try to validate the plugin's archive is not corrupted.
    A valid plugin is a wagon (http://github.com/cloudify-cosomo/wagon)
    in the tar.gz format.
    """
    logger = get_logger()

    logger.info('Validating plugin {0}...'.format(plugin_path.name))
    if not tarfile.is_tarfile(plugin_path.name):
        raise CloudifyCliError('Archive {0} is of an unsupported type. Only '
                               'tar.gz is allowed'.format(plugin_path.name))
    with tarfile.open(plugin_path.name, 'r') as tar:
        tar_members = tar.getmembers()
        package_json_path = "{0}/{1}".format(tar_members[0].name,
                                             'package.json')
        try:
            package_member = tar.getmember(package_json_path)
        except KeyError:
            raise CloudifyCliError(
                'Failed to validate plugin {0} '
                '(package.json was not found in archive)'.format(plugin_path))
        try:
            tar.extractfile(package_member).read()
        except:
            raise CloudifyCliError(
                'Failed to validate plugin {0} '
                '(unable to read package.json)'.format(plugin_path))

    logger.info('Plugin validated successfully')


@plugins.command(name='delete')
@click.argument('plugin-id', required=True)
@click.option('-f',
              '--force',
              is_flag=True,
              help=helptexts.FORCE_DELETE_PLUGIN)
def delete(plugin_id, force):
    """Delete a plugin from the manager
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info('Deleting plugin {0}...'.format(plugin_id))
    client.plugins.delete(plugin_id=plugin_id, force=force)

    logger.info('Plugin deleted')


@plugins.command(name='upload')
@click.argument('plugin-path', required=True)
def upload(plugin_path):
    """Upload a plugin to the manager
    """
    server_ip = utils.get_management_server_ip()
    utils.upload_plugin(plugin_path, server_ip,
                        utils.get_rest_client(server_ip), validate)


@plugins.command(name='download')
@click.argument('plugin-id', required=True)
@click.option('-o',
              '--output-path',
              help=helptexts.OUTPUT_PATH)
def download(plugin_id, output_path):
    """Download a plugin from the manager
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info('Downloading plugin {0}...'.format(plugin_id))
    client = utils.get_rest_client(management_ip)
    target_file = client.plugins.download(plugin_id, output_path)
    logger.info('Plugin downloaded as {0}'.format(target_file))


fields = ['id', 'package_name', 'package_version', 'supported_platform',
          'distribution', 'distribution_release', 'uploaded_at']


@plugins.command(name='get')
@click.argument('plugin-id', required=True)
def get(plugin_id):
    """Retrieve information for a specific plugin
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info('Retrieving plugin {0}...'.format(plugin_id))
    plugin = client.plugins.get(plugin_id, _include=fields)

    pt = utils.table(fields, data=[plugin])
    print_table('Plugin:', pt)


@plugins.command(name='ls')
def ls():
    """List all plugins on the manager
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info('Listing all plugins...')
    plugins = client.plugins.list(_include=fields)

    pt = utils.table(fields, data=plugins)
    print_table('Plugins:', pt)
