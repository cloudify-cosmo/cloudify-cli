########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import tarfile
from urlparse import urlparse

from .. import utils
from ..table import print_data
from ..cli import helptexts, cfy
from ..constants import RESOURCE_LABELS
from ..exceptions import CloudifyCliError


PLUGIN_COLUMNS = ['id', 'package_name', 'package_version', 'distribution',
                  'supported_platform', 'distribution_release', 'uploaded_at',
                  'resource_availability', 'tenant_name', 'created_by']
EXCLUDED_COLUMNS = ['archive_name', 'distribution_version', 'excluded_wheels',
                    'package_source', 'supported_py_versions', 'wheels']


@cfy.group(name='plugins')
@cfy.options.verbose()
def plugins():
    """Handle plugins on the manager
    """
    pass


@plugins.command(name='validate',
                 short_help='Validate a plugin')
@cfy.argument('plugin-path')
@cfy.options.verbose()
@cfy.pass_logger
def validate(plugin_path, logger):
    """Validate a plugin

    This will try to validate the plugin's archive is not corrupted.
    A valid plugin is a wagon (http://github.com/cloudify-cosomo/wagon)
    in the tar.gz format.

    `PLUGIN_PATH` is the path to wagon archive to validate.
    """
    logger.info('Validating plugin {0}...'.format(plugin_path))

    if not tarfile.is_tarfile(plugin_path):
        raise CloudifyCliError(
            'Archive {0} is of an unsupported type. Only '
            'tar.gz/wgn is allowed'.format(plugin_path))
    with tarfile.open(plugin_path) as tar:
        tar_members = tar.getmembers()
        package_json_path = "{0}/{1}".format(
            tar_members[0].name, 'package.json')
        # TODO: Find a better way to validate a plugin.
        # This is.. bad.
        try:
            tar.getmember(package_json_path)
        except KeyError:
            raise CloudifyCliError(
                'Failed to validate plugin {0} '
                '(package.json was not found in archive)'.format(plugin_path))

    logger.info('Plugin validated successfully')


@plugins.command(name='delete',
                 short_help='Delete a plugin [manager only]')
@cfy.argument('plugin-id')
@cfy.options.force(help=helptexts.FORCE_DELETE_PLUGIN)
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete(plugin_id, force, logger, client, tenant_name):
    """Delete a plugin from the manager

    `PLUGIN_ID` is the id of the plugin to delete.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Deleting plugin {0}...'.format(plugin_id))
    client.plugins.delete(plugin_id=plugin_id, force=force)
    logger.info('Plugin deleted')


@plugins.command(name='upload',
                 short_help='Upload a plugin [manager only]')
@cfy.argument('plugin-path')
@cfy.options.private_resource
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.pass_context
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def upload(ctx, plugin_path, private_resource, logger, client, tenant_name):
    """Upload a plugin to the manager

    `PLUGIN_PATH` is the path to wagon archive to upload.
    """
    # Test whether the path is a valid URL. If it is, no point in doing local
    # validations - it will be validated on the server side anyway
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    parsed_url = urlparse(plugin_path)
    if not parsed_url.scheme or not parsed_url.netloc:
        ctx.invoke(validate, plugin_path=plugin_path)

    progress_handler = utils.generate_progress_handler(plugin_path, '')
    logger.info('Uploading plugin {0}...'.format(plugin_path))
    plugin = client.plugins.upload(plugin_path,
                                   private_resource,
                                   progress_handler)
    logger.info("Plugin uploaded. The plugin's id is {0}".format(plugin.id))


@plugins.command(name='download',
                 short_help='Download a plugin [manager only]')
@cfy.argument('plugin-id')
@cfy.options.output_path
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.pass_logger
@cfy.pass_client()
def download(plugin_id, output_path, logger, client, tenant_name):
    """Download a plugin from the manager

    `PLUGIN_ID` is the id of the plugin to download.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Downloading plugin {0}...'.format(plugin_id))
    plugin_name = output_path if output_path else plugin_id
    progress_handler = utils.generate_progress_handler(plugin_name, '')
    target_file = client.plugins.download(plugin_id,
                                          output_path,
                                          progress_handler)
    logger.info('Plugin downloaded as {0}'.format(target_file))


@plugins.command(name='get',
                 short_help='Retrieve plugin information [manager only]')
@cfy.argument('plugin-id')
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get(plugin_id, logger, client, tenant_name):
    """Retrieve information for a specific plugin

    `PLUGIN_ID` is the id of the plugin to get information on.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Retrieving plugin {0}...'.format(plugin_id))
    plugin = client.plugins.get(plugin_id)
    _transform_plugin_response(plugin)
    print_data(PLUGIN_COLUMNS, plugin, 'Plugin:', labels=RESOURCE_LABELS)


@plugins.command(name='list',
                 short_help='List plugins [manager only]')
@cfy.options.sort_by('uploaded_at')
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='plugin')
@cfy.options.all_tenants
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by, descending, tenant_name, all_tenants, logger, client):
    """List all plugins on the manager
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Listing all plugins...')
    plugins_list = client.plugins.list(sort=sort_by,
                                       is_descending=descending,
                                       _all_tenants=all_tenants)
    for plugin in plugins_list:
        _transform_plugin_response(plugin)
    print_data(PLUGIN_COLUMNS,
               plugins_list,
               'Plugins:',
               labels=RESOURCE_LABELS)


def _transform_plugin_response(plugin):
    """Remove any columns that shouldn't be displayed in the CLI
    """
    for column in EXCLUDED_COLUMNS:
        plugin.pop(column, None)
