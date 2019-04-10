########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

import wagon

from cloudify_cli import execution_events_fetcher
from cloudify_cli.logger import get_events_logger
from cloudify_cli.exceptions import SuppressedCloudifyCliError

from cloudify_rest_client.constants import VISIBILITY_EXCEPT_PRIVATE

from .. import utils
from ..table import print_data, print_single
from ..cli import helptexts, cfy
from ..utils import (prettify_client_error,
                     get_visibility,
                     validate_visibility)

PLUGIN_COLUMNS = ['id', 'package_name', 'package_version', 'distribution',
                  'supported_platform', 'distribution_release', 'uploaded_at',
                  'visibility', 'tenant_name', 'created_by', 'yaml_url_path']
PLUGINS_UPDATE_COLUMNS = ['id', 'state', 'blueprint_id', 'temp_blueprint_id',
                          'execution_id', 'deployments_to_update',
                          'visibility', 'created_at', 'forced']
GET_DATA_COLUMNS = ['file_server_path']
EXCLUDED_COLUMNS = ['archive_name', 'distribution_version', 'excluded_wheels',
                    'package_source', 'supported_py_versions', 'wheels']


@cfy.group(name='plugins')
@cfy.options.common_options
def plugins():
    """Handle plugins on the manager
    """
    pass


@plugins.command(name='validate',
                 short_help='Validate a plugin')
@cfy.argument('plugin-path')
@cfy.options.common_options
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
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete(plugin_id, force, logger, client, tenant_name):
    """Delete a plugin from the manager

    `PLUGIN_ID` is the id of the plugin to delete.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Deleting plugin {0}...'.format(plugin_id))
    client.plugins.delete(plugin_id=plugin_id, force=force)
    logger.info('Plugin deleted')


@plugins.command(name='upload',
                 short_help='Upload a plugin [manager only]')
@cfy.argument('plugin-path')
@cfy.options.plugin_yaml_path()
@cfy.options.private_resource
@cfy.options.visibility()
@cfy.options.common_options
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
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Creating plugin zip archive..')
    wagon_path = utils.get_local_path(plugin_path, create_temp=True)
    yaml_path = utils.get_local_path(yaml_path, create_temp=True)
    zip_path = utils.zip_files([wagon_path, yaml_path])

    progress_handler = utils.generate_progress_handler(zip_path, '')

    visibility = get_visibility(private_resource, visibility, logger)
    logger.info('Uploading plugin archive (wagon + yaml)..')
    try:
        plugin = client.plugins.upload(zip_path,
                                       visibility,
                                       progress_handler)
        logger.info("Plugin uploaded. Plugin's id is {0}".format(plugin.id))
    finally:
        os.remove(wagon_path)
        os.remove(yaml_path)
        os.remove(zip_path)


@plugins.command(name='bundle-upload',
                 short_help='Upload a bundle of plugins [manager only]')
@cfy.options.plugins_bundle_path
@cfy.pass_client()
@cfy.pass_logger
def upload_caravan(client, logger, path):
    if not path:
        logger.info("Starting upload of plugins bundle, "
                    "this may take few minutes to complete.")
        path = 'http://repository.cloudifysource.org/' \
               'cloudify/wagons/cloudify-plugins-bundle.tgz'
    progress = utils.generate_progress_handler(path, '')
    plugins_ = client.plugins.upload(path, progress_callback=progress)
    logger.info("Bundle uploaded, {0} Plugins installed."
                .format(len(plugins_)))
    if len(plugins_) > 0:
        logger.info("The plugins' ids are:\n{0}\n".
                    format('\n'.join([p.id for p in plugins_])))


@plugins.command(name='download',
                 short_help='Download a plugin [manager only]')
@cfy.argument('plugin-id')
@cfy.options.output_path
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.pass_logger
@cfy.pass_client()
def download(plugin_id, output_path, logger, client, tenant_name):
    """Download a plugin from the manager

    `PLUGIN_ID` is the id of the plugin to download.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
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
@cfy.options.common_options
@cfy.options.get_data
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get(plugin_id, logger, client, tenant_name, get_data):
    """Retrieve information for a specific plugin

    `PLUGIN_ID` is the id of the plugin to get information on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving plugin {0}...'.format(plugin_id))
    plugin = client.plugins.get(plugin_id, _get_data=get_data)
    _transform_plugin_response(plugin)
    columns = PLUGIN_COLUMNS + GET_DATA_COLUMNS if get_data else PLUGIN_COLUMNS
    print_single(columns, plugin, 'Plugin:')


@plugins.command(name='list',
                 short_help='List plugins [manager only]')
@cfy.options.sort_by('uploaded_at')
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='plugin')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.common_options
@cfy.options.get_data
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by,
         descending,
         tenant_name,
         all_tenants,
         search,
         pagination_offset,
         pagination_size,
         logger,
         client,
         get_data):
    """List all plugins on the manager
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing all plugins...')
    plugins_list = client.plugins.list(sort=sort_by,
                                       is_descending=descending,
                                       _all_tenants=all_tenants,
                                       _search=search,
                                       _get_data=get_data,
                                       _offset=pagination_offset,
                                       _size=pagination_size)
    for plugin in plugins_list:
        _transform_plugin_response(plugin)
    columns = PLUGIN_COLUMNS + GET_DATA_COLUMNS if get_data else PLUGIN_COLUMNS
    print_data(columns, plugins_list, 'Plugins:')
    total = plugins_list.metadata.pagination.total
    logger.info('Showing {0} of {1} plugins'.format(len(plugins_list),
                                                    total))


def _transform_plugin_response(plugin):
    """Remove any columns that shouldn't be displayed in the CLI
    """
    for column in EXCLUDED_COLUMNS:
        plugin.pop(column, None)


@plugins.command(name='set-global',
                 short_help="Set the plugin's visibility to global")
@cfy.argument('plugin-id')
@cfy.options.common_options
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
@cfy.options.common_options
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


@plugins.command(name='update',
                 short_help='Update the plugins of all the deployments of '
                            'the blueprint [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.assert_manager_active()
@cfy.options.include_logs
@cfy.options.json_output
@cfy.pass_logger
@cfy.pass_client()
@cfy.options.force(help=helptexts.FORCE_PLUGINS_UPDATE)
def update(blueprint_id,
           include_logs,
           json_output,
           logger,
           client,
           tenant_name,
           force):
    """Update the plugins of all the deployments of the given blueprint. This
    will update the deployments one by one until all succeeded.

    `BLUEPRINT_ID` the blueprint's ID to perform the plugins update with.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Updating the plugins of the deployments of the blueprint '
                '{}'.format(blueprint_id))
    plugins_update = client.plugins_update.update_plugins(blueprint_id, force)
    events_logger = get_events_logger(json_output)
    execution = execution_events_fetcher.wait_for_execution(
        client,
        client.executions.get(plugins_update.execution_id),
        events_handler=events_logger,
        include_logs=include_logs,
        timeout=None  # don't timeout ever
    )

    if execution.error:
        logger.info("Execution of workflow '{0}' for blueprint "
                    "'{1}' failed. [error={2}]"
                    .format(execution.workflow_id,
                            blueprint_id,
                            execution.error))
        logger.info('Failed updating plugins for blueprint {0}. '
                    'Plugins update ID: {1}. Execution id: {2}'
                    .format(blueprint_id,
                            plugins_update.id,
                            execution.id))
        raise SuppressedCloudifyCliError()
    logger.info("Finished executing workflow '{0}'".format(
        execution.workflow_id))
    logger.info('Successfully updated plugins for blueprint {0}. '
                'Plugins update ID: {1}. Execution id: {2}'
                .format(blueprint_id,
                        plugins_update.id,
                        execution.id))


@plugins.command(
    name='get-update',
    short_help='Retrieve plugins update information [manager only]'
)
@cfy.argument('plugins-update-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='plugins update')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_get_update(plugins_update_id, logger, client, tenant_name):
    """Retrieve information for a specific plugins update

    `PLUGINS_UPDATE_ID` is the id of the plugins update to get information on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving plugins update {0}...'.format(plugins_update_id))
    plugins_update_dict = client.plugins_update.get(plugins_update_id)
    print_single(
        PLUGINS_UPDATE_COLUMNS, plugins_update_dict, 'Plugins update:')


@plugins.command(name='history', short_help='List plugins updates '
                                            '[manager only]')
@cfy.options.blueprint_id()
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='plugins update')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_history(blueprint_id,
                    sort_by,
                    descending,
                    all_tenants,
                    search,
                    pagination_offset,
                    pagination_size,
                    logger,
                    client,
                    tenant_name):
    """Show blueprint history by listing plugins updates

    If `--blueprint-id` is provided, list plugins updates for that
    blueprint. Otherwise, list plugins updates for all blueprints.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    if blueprint_id:
        logger.info('Listing plugins updates for blueprint {0}...'.format(
            blueprint_id))
    else:
        logger.info('Listing all plugins updates...')

    plugins_updates = client.plugins_update.list(
        sort=sort_by,
        is_descending=descending,
        _all_tenants=all_tenants,
        _search=search,
        _offset=pagination_offset,
        _size=pagination_size,
        blueprint_id=blueprint_id
    )
    total = plugins_updates.metadata.pagination.total
    print_data(
        PLUGINS_UPDATE_COLUMNS, plugins_updates, 'Plugins updates:')
    logger.info('Showing {0} of {1} plugins updates'.format(
        len(plugins_updates), total))
