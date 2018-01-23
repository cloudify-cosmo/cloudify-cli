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
import os
import tarfile
import tempfile

import shutil
import yaml

import wagon

from cloudify_rest_client.constants import VISIBILITY_EXCEPT_PRIVATE

from .. import utils
from ..table import print_data
from ..cli import helptexts, cfy
from ..utils import (prettify_client_error,
                     get_visibility,
                     validate_visibility)
from ..exceptions import CloudifyCliError

PLUGIN_COLUMNS = ['id', 'package_name', 'package_version', 'distribution',
                  'supported_platform', 'distribution_release', 'uploaded_at',
                  'visibility', 'tenant_name', 'created_by', 'yaml_url_path']
GET_DATA_COLUMNS = ['file_server_path']
EXCLUDED_COLUMNS = ['archive_name', 'distribution_version', 'excluded_wheels',
                    'package_source', 'supported_py_versions', 'wheels']


def _create_caravan(mappings, dest, name=None):
    tempdir = tempfile.mkdtemp()
    metadata = {}

    for wgn_path, yaml_path in mappings.iteritems():
        plugin_root_dir = os.path.basename(wgn_path).split('.', 1)[0]
        os.mkdir(os.path.join(tempdir, plugin_root_dir))

        dest_wgn_path = os.path.join(plugin_root_dir,
                                     os.path.basename(wgn_path))
        dest_yaml_path = os.path.join(plugin_root_dir,
                                      os.path.basename(yaml_path))

        wgn_path = utils.get_local_path(wgn_path)
        yaml_path = utils.get_local_path(yaml_path)

        shutil.copy(wgn_path, os.path.join(tempdir, dest_wgn_path))
        shutil.copy(yaml_path, os.path.join(tempdir, dest_yaml_path))
        metadata[dest_wgn_path] = dest_yaml_path

    with open(os.path.join(tempdir, 'METADATA'), 'w+') as f:
        yaml.dump(metadata, f)

    tar_name = name or 'palace'
    tar_path = os.path.join(dest, '{0}.cvn'.format(tar_name))
    tarfile_ = tarfile.open(tar_path, 'w:gz')
    try:
        tarfile_.add(tempdir, arcname=tar_name)
    finally:
        tarfile_.close()
        shutil.rmtree(tempdir)

    return tar_path


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
    wagon.validate(plugin_path)
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
@cfy.options.plugin_yaml_path()
@cfy.options.private_resource
@cfy.options.visibility()
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.pass_context
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def upload(ctx,
           plugin_path,
           yaml_path,
           private_resource,
           visibility,
           logger,
           client,
           tenant_name):
    """Upload a plugin to the manager

    `PLUGIN_PATH` is the path to wagon archive to upload.
    """
    # Test whether the path is a valid URL. If it is, no point in doing local
    # validations - it will be validated on the server side anyway
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))

    logger.info('Creating plugin zip archive..')
    plugin_path = utils.get_local_path(plugin_path)
    yaml_path = utils.get_local_path(yaml_path)
    plugin_path = utils.zip_files([plugin_path, yaml_path])

    progress_handler = utils.generate_progress_handler(plugin_path, '')

    visibility = get_visibility(private_resource, visibility, logger)
    logger.info('Uploading plugin archive (wagon + yaml)..')
    plugin = client.plugins.upload(plugin_path,
                                   visibility,
                                   progress_handler)
    logger.info("Plugin uploaded. The plugin's id is {0}".format(plugin.id))
    os.remove(plugin_path)


@plugins.command(name='create-caravan',
                 short_help='Create a bundle of plugins')
@cfy.options.caravan_name
@cfy.argument('plugin-mappings')
@cfy.argument('destination')
@cfy.pass_logger
def create_caravan(logger, plugin_mappings, destination, name):
    logger.info('Packing wagons into a Caravan')
    try:
        plugin_mappings = yaml.load(
            open(utils.get_local_path(plugin_mappings)))
    except CloudifyCliError:
        plugin_mappings = yaml.load(plugin_mappings)

    cvn_path = _create_caravan(plugin_mappings, destination, name)
    logger.info('Caravan created at {0}'.format(cvn_path))
    return cvn_path


@plugins.command(name='upload-caravan',
                 short_help='Upload a bundle of plugins')
@cfy.argument('caravan-path')
@cfy.pass_client()
def upload_caravan(client, caravan_path):
    progress = utils.generate_progress_handler(caravan_path, '')
    return client.plugins.upload(caravan_path, progress_callback=progress)


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
@cfy.options.get_data
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get(plugin_id, logger, client, tenant_name, get_data):
    """Retrieve information for a specific plugin

    `PLUGIN_ID` is the id of the plugin to get information on.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Retrieving plugin {0}...'.format(plugin_id))
    plugin = client.plugins.get(plugin_id, _get_data=get_data)
    _transform_plugin_response(plugin)
    columns = PLUGIN_COLUMNS + GET_DATA_COLUMNS if get_data else PLUGIN_COLUMNS
    print_data(columns, plugin, 'Plugin:')


@plugins.command(name='list',
                 short_help='List plugins [manager only]')
@cfy.options.sort_by('uploaded_at')
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='plugin')
@cfy.options.all_tenants
@cfy.options.verbose()
@cfy.options.get_data
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by,
         descending,
         tenant_name,
         all_tenants,
         logger,
         client,
         get_data):
    """List all plugins on the manager
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Listing all plugins...')
    plugins_list = client.plugins.list(sort=sort_by,
                                       is_descending=descending,
                                       _all_tenants=all_tenants,
                                       _get_data=get_data)
    for plugin in plugins_list:
        _transform_plugin_response(plugin)
    columns = PLUGIN_COLUMNS + GET_DATA_COLUMNS if get_data else PLUGIN_COLUMNS
    print_data(columns, plugins_list, 'Plugins:')


def _transform_plugin_response(plugin):
    """Remove any columns that shouldn't be displayed in the CLI
    """
    for column in EXCLUDED_COLUMNS:
        plugin.pop(column, None)


@plugins.command(name='set-global',
                 short_help="Set the plugin's visibility to global")
@cfy.argument('plugin-id')
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_global(plugin_id, logger, client):
    """Set the plugin's visibility to global

    `PLUGIN_ID` is the id of the plugin to set global
    """
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        client.plugins.set_global(plugin_id)
        logger.info('Plugin `{0}` was set to global'.format(plugin_id))
        logger.info("This command will be deprecated soon, please use the "
                    "'set-visibility' command instead")


@plugins.command(name='set-visibility',
                 short_help="Set the plugin's visibility")
@cfy.argument('plugin-id')
@cfy.options.visibility(required=True, valid_values=VISIBILITY_EXCEPT_PRIVATE)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_visibility(plugin_id, visibility, logger, client):
    """Set the plugin's visibility

    `PLUGIN_ID` is the id of the plugin to update
    """
    validate_visibility(visibility, valid_values=VISIBILITY_EXCEPT_PRIVATE)
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        client.plugins.set_visibility(plugin_id, visibility)
        logger.info('Plugin `{0}` was set to {1}'.format(plugin_id,
                                                         visibility))
