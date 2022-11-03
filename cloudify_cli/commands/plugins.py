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

import json
import os
import time

import click
import wagon

from cloudify.models_states import PluginInstallationState

from cloudify_cli import execution_events_fetcher
from cloudify_cli.logger import get_events_logger, CloudifyJSONEncoder, output
from cloudify_cli.exceptions import (
    SuppressedCloudifyCliError, CloudifyCliError, CloudifyValidationError,
)

from cloudify_rest_client.client import CLOUDIFY_TENANT_HEADER
from cloudify_rest_client.constants import VISIBILITY_EXCEPT_PRIVATE
from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_cli import env, utils
from cloudify_cli.cli import helptexts, cfy
from cloudify_cli.labels_utils import get_printable_resource_labels
from cloudify_cli.logger import get_global_json_output
from cloudify_cli.table import print_data, print_single, print_details
from cloudify_cli.utils import (
    prettify_client_error,
    get_visibility,
    validate_visibility)

PLUGINS_BUNDLE_COLUMNS = ['id', 'package_name', 'package_version',
                          'distribution', 'distribution_release']
PLUGIN_COLUMNS = PLUGINS_BUNDLE_COLUMNS + \
                 ['installed on', 'uploaded_at', 'visibility', 'tenant_name',
                  'created_by', 'yaml_url_path']
PLUGINS_UPDATE_COLUMNS = ['id', 'state', 'blueprint_id', 'temp_blueprint_id',
                          'execution_id', 'deployments_to_update',
                          'visibility', 'created_at', 'forced']
GET_DATA_COLUMNS = ['file_server_path', 'supported_platform',
                    'supported_py_versions']


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
    logger.info('Validating plugin %s...', plugin_path)
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
    logger.info('Deleting plugin %s...', plugin_id)
    client.plugins.delete(plugin_id=plugin_id, force=force)
    logger.info('Plugin deleted')


@plugins.command(name='upload',
                 short_help='Upload a plugin [manager only]')
@cfy.argument('plugin-path')
@cfy.options.plugin_yaml_path()
@cfy.options.plugin_icon_path()
@cfy.options.plugin_title()
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
           icon_path,
           title,
           private_resource,
           visibility,
           logger,
           client,
           tenant_name):
    """Upload a plugin to the manager

    `PLUGIN_PATH` is the path to wagon archive to upload.
    """
    if client.manager.get_version().get('edition') == 'premium':
        client.license.check()
    # Test whether the path is a valid URL. If it is, no point in doing local
    # validations - it will be validated on the server side anyway
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Creating plugin zip archive..')
    wagon_path = utils.get_local_path(plugin_path, create_temp=True)
    zip_files = [wagon_path] + \
                [utils.get_local_path(p, create_temp=True) for p in yaml_path]
    zip_descr = 'wagon + yaml'
    if icon_path:
        icon_path = utils.get_local_path(icon_path,
                                         destination='icon.png',
                                         create_temp=True)
        zip_files.append(icon_path)
        zip_descr += ' + icon'
    zip_path = utils.zip_files(zip_files)

    progress_handler = utils.generate_progress_handler(zip_path, '')

    visibility = get_visibility(private_resource, visibility, logger)
    logger.info('Uploading plugin archive (%s)..', zip_descr)

    try:
        plugin = client.plugins.upload(zip_path,
                                       plugin_title=title,
                                       visibility=visibility,
                                       progress_callback=progress_handler)
        logger.info("Plugin uploaded. Plugin's id is %s", plugin.id)
    finally:
        for f in zip_files:
            os.remove(f)
            f_dir = os.path.dirname(f)
            if os.path.exists(f_dir) and os.path.isdir(f_dir):
                os.rmdir(f_dir)
        os.remove(zip_path)


@plugins.command(name='bundle-upload',
                 short_help='Upload a bundle of plugins [manager only]')
@cfy.options.plugins_bundle_path
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def upload_caravan(client, logger, path):
    if client.manager.get_version().get('edition') == 'premium':
        client.license.check()
    if not path:
        logger.info("Starting upload of plugins bundle, "
                    "this may take few minutes to complete.")
        path = 'http://repository.cloudifysource.org/' \
               'cloudify/wagons/cloudify-plugins-bundle.tgz'
    progress = utils.generate_progress_handler(path, '')
    plugins_ = client.plugins.upload(path, progress_callback=progress)
    logger.info("Bundle uploaded, %d Plugins installed.", len(plugins_))
    if len(plugins_) > 0:
        print_data(PLUGINS_BUNDLE_COLUMNS, plugins_, 'Plugins:')


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
    logger.info('Downloading plugin %s...', plugin_id)
    plugin_name = output_path if output_path else plugin_id
    progress_handler = utils.generate_progress_handler(plugin_name, '')
    target_file = client.plugins.download(plugin_id,
                                          output_path,
                                          progress_handler)
    logger.info('Plugin downloaded as %s', target_file)


@plugins.command(name='download_yaml',
                 short_help='Download a plugin yaml [manager only]')
@cfy.argument('plugin-id')
@cfy.options.output_path
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.pass_logger
@cfy.pass_client()
def download_yaml(plugin_id, output_path, logger, client, tenant_name):
    """Download a plugin yaml from the manager

    `PLUGIN_ID` is the id of the plugin yaml to download.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Downloading plugin yaml %s...', plugin_id)
    plugin_name = output_path if output_path else plugin_id
    progress_handler = utils.generate_progress_handler(plugin_name, '')
    target_file = client.plugins.download_yaml(plugin_id,
                                               output_path,
                                               progress_handler)
    logger.info('Plugin yaml downloaded as %s', target_file)


def _format_installation_state(plugin):
    """Format the 'installation_state' into a human-readable 'installed on'"""
    if not plugin.get('installation_state'):
        return ''
    agents = 0
    managers = 0
    errors = 0
    for state in plugin['installation_state']:
        if state['state'] == PluginInstallationState.ERROR:
            errors += 1
        elif state['state'] != PluginInstallationState.INSTALLED:
            continue

        if state.get('manager'):
            managers += 1
        elif state.get('agent'):
            agents += 1
    parts = []
    if managers:
        parts.append('{0} managers'.format(managers))
    if agents:
        parts.append('{0} agents'.format(agents))
    if errors:
        parts.append('{0} errors'.format(errors))
    return ', '.join(parts)


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
    logger.info('Retrieving plugin %s...', plugin_id)
    plugin = client.plugins.get(plugin_id, _get_data=get_data)
    columns = PLUGIN_COLUMNS + GET_DATA_COLUMNS if get_data else PLUGIN_COLUMNS
    plugin['installed on'] = _format_installation_state(plugin)

    if get_global_json_output():
        # for json, also include installation_state because it's useful
        print_single(columns + ['installation_state'], plugin, 'Plugin:', 50)
        return

    states = {}
    for state in plugin.pop('installation_state', []):
        if state.get('manager'):
            label = 'Manager {0}'.format(state['manager'])
        elif state.get('agent'):
            label = 'Agent {0}'.format(state['agent'])
        states[label] = state['state']
    print_details({
        col: plugin.get(col) for col in columns
    }, 'Plugin:')
    print_details(states, 'Plugin installation state:')


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
@cfy.options.extended_view
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
        plugin['installed on'] = _format_installation_state(plugin)
    columns = PLUGIN_COLUMNS + GET_DATA_COLUMNS if get_data else PLUGIN_COLUMNS

    if get_global_json_output():
        columns += ['installation_state']

    print_data(columns, plugins_list, 'Plugins:')
    total = plugins_list.metadata.pagination.total
    logger.info('Showing %d of %d plugins', len(plugins_list), total)


def _wait_for_plugin_to_be_installed(client, plugin_id, managers, agents,
                                     timeout, logger):
    logger.info(
        'Waiting for plugin %s to be installed on the managers: [%s] '
        'and agents: [%s]',
        plugin_id, ', '.join(managers), ', '.join(agents)
    )
    wait_managers = set(managers)
    wait_agents = set(agents)
    errors = 0
    deadline = time.time() + timeout
    while time.time() < deadline:
        for pstate in client.plugins.get(plugin_id)['installation_state']:

            if pstate['state'] == PluginInstallationState.INSTALLED:
                if pstate.get('manager') in wait_managers:
                    wait_managers.remove(pstate['manager'])
                    logger.info('Finished installing on manager %s',
                                pstate['manager'])
                if pstate.get('agent') in wait_agents:
                    wait_agents.remove(pstate['agent'])
                    logger.info('Finished installing on agent %s',
                                pstate['agent'])

            if pstate['state'] == PluginInstallationState.ERROR:
                if pstate.get('manager') in wait_managers:
                    errors += 1
                    wait_managers.remove(pstate['manager'])
                    logger.info('Error installing on manager %s: %s',
                                pstate['manager'], pstate['error'])
                if pstate.get('agent') in wait_agents:
                    errors += 1
                    wait_agents.remove(pstate['agent'])
                    logger.info('Error installing on agent %s: %s',
                                pstate['agent'], pstate['error'])

        if not wait_managers and not wait_agents:
            break
        time.sleep(1)
    else:
        raise CloudifyCliError(
            'Timed out waiting for plugin {0} to be installed on managers: '
            '[{1}] and agents: [{2}]'
            .format(plugin_id,
                    ', '.join(managers),
                    ', '.join(agents))
        )
    if errors:
        raise CloudifyCliError('Encountered errors while installing plugins')


@plugins.command(name='install',
                 short_help='Install a plugin [manager only]')
@cfy.argument('plugin-id')
@cfy.options.common_options
@click.option('--manager-hostname', multiple=True,
              help='The hostname of the manager to install the plugin on '
                   '(can be passed multiple times)')
@click.option('--agent-name', multiple=True,
              help='The name of the agent to install the plugin on'
                   '(can be passed multiple times)')
@cfy.options.timeout(300)
@cfy.pass_client()
@cfy.pass_logger
def install(plugin_id, manager_hostname, agent_name, timeout, client, logger):
    """Install the plugin on the given managers and agents.

    Force plugin installation before it needs to be used.
    If manager hostnames and agent names are not provided, default to
    installing on all managers.

    This will wait for the plugins to be installed, up to timeout seconds.
    """
    if not manager_hostname and not agent_name:
        manager_hostname = [
            manager.hostname for manager in client.manager.get_managers()
        ]

    client.plugins.install(
        plugin_id,
        agents=agent_name,
        managers=manager_hostname
    )
    _wait_for_plugin_to_be_installed(
        client, plugin_id, manager_hostname, agent_name, timeout, logger)


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
        logger.info('Plugin `%s` was set to global', plugin_id)
        logger.warning("This command is deprecated and will be removed soon, "
                       "please use the 'set-visibility' command instead")


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
        logger.info('Plugin `%s` was set to %s', plugin_id, visibility)


@plugins.command(name='set-owner',
                 short_help="Change plugin's ownership")
@cfy.argument('plugin-id')
@cfy.options.new_username()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_owner(plugin_id, username, logger, client):
    """Set a new owner for the plugin."""
    plugin = client.plugins.set_owner(plugin_id, username)
    logger.info('Plugin `%s` is now owned by user `%s`.',
                plugin_id, plugin.get('created_by'))


@plugins.command(name='update',
                 short_help='Update the plugins of all the deployments of '
                            'the blueprint [manager only]')
@cfy.argument('blueprint-id', required=False)
@cfy.options.all_blueprints
@cfy.options.all_tenants
@cfy.options.except_blueprints
@cfy.options.plugin_names
@cfy.options.plugins_to_latest
@cfy.options.plugins_all_to_latest
@cfy.options.plugins_to_minor
@cfy.options.plugins_all_to_minor
@cfy.options.common_options
@cfy.options.tenant_name(required=False,
                         mutually_exclusive_with=['all_tenants'],
                         resource_name_for_help='plugin')
@cfy.assert_manager_active()
@cfy.options.include_logs
@cfy.options.json_output
@cfy.pass_logger
@cfy.pass_client()
@cfy.options.force(help=helptexts.FORCE_PLUGINS_UPDATE)
@cfy.options.auto_correct_types
@cfy.options.reevaluate_active_statuses(help=helptexts.
                                        REEVALUATE_ACTIVE_STATUSES_PLUGINS)
def update(blueprint_id,
           all_blueprints,
           all_tenants,
           except_blueprints,
           plugin_names,
           to_latest,
           all_to_latest,
           to_minor,
           all_to_minor,
           include_logs,
           json_output,
           logger,
           client,
           tenant_name,
           force,
           auto_correct_types,
           reevaluate_active_statuses):
    """Update the plugins of all the deployments of the given blueprint
    or any blueprint in case `--all-blueprints` flag was used instead of
    providing a BLUEPRINT_ID.  This will update the deployments one by one
    until all succeeded.
    """
    # Validate input arguments
    if ((blueprint_id and all_blueprints) or
            (not blueprint_id and not all_blueprints)):
        raise CloudifyValidationError(
            'ERROR: Invalid command syntax. Either provide '
            'a BLUEPRINT_ID or use --all-blueprints flag.')
    if except_blueprints and not all_blueprints:
        raise CloudifyValidationError(
            'ERROR: Invalid command syntax. Cannot list blueprints '
            'exceptions unless used with --all-blueprints flag.')
    all_to_minor = bool(all_to_minor)
    if all_to_latest is None:
        all_to_latest = not all_to_minor
    if (all_to_latest and all_to_minor) or \
            (not all_to_latest and not all_to_minor):
        raise CloudifyValidationError(
            'ERROR: Invalid command syntax.  --all-to-latest and '
            '--all-to-minor are mutually exclusive.')
    if to_latest and all_to_latest:
        raise CloudifyValidationError(
            'ERROR: Invalid command syntax.  --all-to-latest and '
            '--to-latest are mutually exclusive.  If you want to upgrade '
            'only the specific plugins, use --plugin-name parameter instead.')
    if to_minor and all_to_minor:
        raise CloudifyValidationError(
            'ERROR: Invalid command syntax.  --all-to-minor and '
            '--to-minor are mutually exclusive.  If you want to upgrade '
            'only the specific plugins, use --plugin-name parameter instead.')

    if blueprint_id:
        _update_a_blueprint(
            blueprint_id,
            plugin_names,
            to_latest,
            all_to_latest,
            to_minor,
            all_to_minor,
            include_logs,
            json_output,
            logger,
            force,
            auto_correct_types,
            reevaluate_active_statuses,
            client,
            tenant_name,
        )
    elif all_blueprints:
        update_results = {'successful': [], 'failed': []}
        pagination_offset = 0
        while True:
            blueprints = client.blueprints.list(
                sort=['tenant_name', 'created_at'],
                _all_tenants=all_tenants,
                _offset=pagination_offset,
            )
            for blueprint in blueprints:
                if blueprint.id in except_blueprints:
                    continue
                try:
                    _update_a_blueprint(blueprint.id,
                                        plugin_names,
                                        to_latest,
                                        all_to_latest,
                                        to_minor,
                                        all_to_minor,
                                        include_logs,
                                        json_output,
                                        logger,
                                        force,
                                        auto_correct_types,
                                        reevaluate_active_statuses,
                                        client,
                                        blueprint.tenant_name)
                    update_results['successful'].append(blueprint.id)
                except (CloudifyClientError, SuppressedCloudifyCliError) as ex:
                    update_results['failed'].append(blueprint.id)
                    logger.warning('Error during %s blueprint update.  %s',
                                   blueprint.id, ex)
            pagination_offset += blueprints.metadata.pagination.size
            if len(blueprints) < blueprints.metadata.pagination.size or \
                    0 == blueprints.metadata.pagination.size:
                break
        if update_results['successful']:
            logger.info('Successfully updated %d blueprints.',
                        len(update_results['successful']))
        if update_results['failed']:
            logger.error('Failed updating %d blueprints.',
                         len(update_results['failed']))
            logger.error('Failed blueprints: %s.',
                         ', '.join(update_results['failed']))


@plugins.command(name='list_updates',
                 short_help='List all plugin updates for the tenant')
@cfy.options.tenant_name(required=False,
                         mutually_exclusive_with=['all_tenants'],
                         resource_name_for_help='plugin')
@cfy.assert_manager_active()
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.sort_by('created_at')
@cfy.options.descending
@cfy.options.get_data
@cfy.pass_logger
@cfy.pass_client()
def updates_list(tenant_name,
                 pagination_offset,
                 pagination_size,
                 sort_by,
                 descending,
                 get_data,
                 logger,
                 client):
    utils.explicit_tenant_name_message(tenant_name, logger)
    updates_list = client.plugins_update.list(sort=sort_by,
                                              is_descending=descending,
                                              _offset=pagination_offset,
                                              _size=pagination_size)
    columns = [
        'id', 'visibility', 'state', 'forced', 'all_tenants',
        'blueprint_id', 'execution_id', 'created_by', 'created_at',
    ]
    if get_data:
        columns.extend(['deployments_to_update', 'deployments_per_tenant',
                        'temp_blueprint_id'])

    print_data(columns, updates_list, 'Plugins updates:')
    total = updates_list.metadata.pagination.total
    logger.info('Showing %d of %d plugins updates', len(updates_list), total)


def _update_a_blueprint(blueprint_id,
                        plugin_names,
                        to_latest,
                        all_to_latest,
                        to_minor,
                        all_to_minor,
                        include_logs,
                        json_output,
                        logger,
                        force,
                        auto_correct_types,
                        reevaluate_active_statuses,
                        client,
                        tenant_name):
    utils.explicit_tenant_name_message(tenant_name, logger)
    client._client._set_header(CLOUDIFY_TENANT_HEADER, tenant_name)
    logger.info('Updating the plugins of the deployments of the blueprint %s',
                blueprint_id)
    plugins_update = client.plugins_update.update_plugins(
        blueprint_id, force=force, plugin_names=plugin_names,
        to_latest=to_latest, all_to_latest=all_to_latest,
        to_minor=to_minor, all_to_minor=all_to_minor,
        auto_correct_types=auto_correct_types,
        reevaluate_active_statuses=reevaluate_active_statuses,
    )
    events_logger = get_events_logger(json_output)
    execution = execution_events_fetcher.wait_for_execution(
        client,
        client.executions.get(plugins_update.execution_id),
        events_handler=events_logger,
        include_logs=include_logs,
        timeout=None  # don't timeout ever
    )

    if execution.error:
        logger.info("Execution of workflow '%s' for blueprint "
                    "'%s' failed. [error=%s]",
                    execution.workflow_id,
                    blueprint_id,
                    execution.error)
        logger.info('Failed updating plugins for blueprint %s. '
                    'Plugins update ID: %s. Execution id: %s',
                    blueprint_id,
                    plugins_update.id,
                    execution.id)
        raise SuppressedCloudifyCliError()
    logger.info("Finished executing workflow '%s'",
                execution.workflow_id)
    logger.info('Successfully updated plugins for blueprint %s. '
                'Plugins update ID: %s. Execution id: %s',
                blueprint_id,
                plugins_update.id,
                execution.id)


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
@cfy.options.extended_view
def manager_get_update(plugins_update_id, logger, client, tenant_name):
    """Retrieve information for a specific plugins update

    `PLUGINS_UPDATE_ID` is the id of the plugins update to get information on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving plugins update %s...', plugins_update_id)
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
@cfy.options.extended_view
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
        logger.info('Listing plugins updates for blueprint %s...',
                    blueprint_id)
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
    logger.info('Showing %d of %d plugins updates',
                len(plugins_updates), total)


@plugins.group(name='blueprint-labels',
               short_help="Handle plugin's blueprint labels")
@cfy.options.common_options
def blueprint_labels():
    if not env.is_initialized():
        env.raise_uninitialized()


@blueprint_labels.command(name='list',
                          short_help="List blueprint-labels of a specific "
                                     "plugin")
@cfy.argument('plugin-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list_blueprint_labels(plugin_id,
                          logger,
                          client,
                          tenant_name):
    _list_metadata(plugin_id, 'blueprint_labels', tenant_name,
                   client.plugins, logger)


@blueprint_labels.command(name='add',
                          short_help="Add blueprint-labels to a specific "
                                     "plugin")
@cfy.argument('labels-list',
              callback=cfy.parse_and_validate_labels)
@cfy.argument('plugin-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_blueprint_labels(labels_list,
                         plugin_id,
                         logger,
                         client,
                         tenant_name):
    """LABELS_LIST: <key>:<value>,<key>:<value>.
    Any comma and colon in <value> must be escaped with '\\'."""
    _add_metadata(plugin_id, 'blueprint_labels', labels_list, tenant_name,
                  client.plugins, logger)


@blueprint_labels.command(name='delete',
                          short_help="Delete blueprint-labels from a specific "
                                     "plugin")
@cfy.argument('label', callback=cfy.parse_and_validate_label_to_delete)
@cfy.argument('plugin-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete_blueprint_labels(label,
                            plugin_id,
                            logger,
                            client,
                            tenant_name):
    """
    LABEL: A mixed list of labels and keys, i.e.
    <key>:<value>,<key>,<key>:<value>. If <key> is provided,
    all labels associated with this key will be deleted from the deployment.
    Any comma and colon in <value> must be escaped with `\\`
    """
    _delete_metadata(plugin_id, 'blueprint_labels', label, tenant_name,
                     client.plugins, logger)


@plugins.group(name='deployment-labels',
               short_help="Handle plugin's (deployment) labels")
@cfy.options.common_options
def deployment_labels():
    if not env.is_initialized():
        env.raise_uninitialized()


@deployment_labels.command(name='list',
                           short_help="List (deployment) labels of a specific "
                                      "plugin")
@cfy.argument('plugin-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list_deployment_labels(plugin_id,
                           logger,
                           client,
                           tenant_name):
    _list_metadata(plugin_id, 'labels', tenant_name, client.plugins, logger)


@deployment_labels.command(name='add',
                           short_help="Add (deployment) labels to a specific "
                                      "plugin")
@cfy.argument('labels-list',
              callback=cfy.parse_and_validate_labels)
@cfy.argument('plugin-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_deployment_labels(labels_list,
                          plugin_id,
                          logger,
                          client,
                          tenant_name):
    """LABELS_LIST: <key>:<value>,<key>:<value>.
    Any comma and colon in <value> must be escaped with '\\'."""
    _add_metadata(plugin_id, 'labels', labels_list, tenant_name,
                  client.plugins, logger)


@deployment_labels.command(name='delete',
                           short_help="Delete (deployment) labels from "
                                      "a specific plugin")
@cfy.argument('label', callback=cfy.parse_and_validate_label_to_delete)
@cfy.argument('plugin-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete_deployment_labels(label,
                             plugin_id,
                             logger,
                             client,
                             tenant_name):
    """
    LABEL: A mixed list of labels and keys, i.e.
    <key>:<value>,<key>,<key>:<value>. If <key> is provided,
    all labels associated with this key will be deleted from the deployment.
    Any comma and colon in <value> must be escaped with `\\`
    """
    _delete_metadata(plugin_id, 'labels', label, tenant_name,
                     client.plugins, logger)


@plugins.group(name='resource-tags',
               short_help="Handle plugin's resource tags")
@cfy.options.common_options
def resource_tags():
    if not env.is_initialized():
        env.raise_uninitialized()


@resource_tags.command(name='list',
                       short_help="List resource tags of a specific plugin")
@cfy.argument('plugin-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list_resource_tags(plugin_id, logger, client, tenant_name):
    _list_metadata(plugin_id, 'resource_tags', tenant_name, client.plugins,
                   logger)


@resource_tags.command(name='add',
                       short_help="Add resource tags to a specific plugin")
@cfy.argument('key-values',
              callback=cfy.parse_and_validate_labels)
@cfy.argument('plugin-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_resource_tags(key_values, plugin_id, logger, client, tenant_name):
    """KEY_VALUES: <key>:<value>,<key>:<value>.
    Any comma and colon in <value> must be escaped with '\\'."""
    _add_metadata(plugin_id, 'resource_tags', key_values, tenant_name,
                  client.plugins, logger)


@resource_tags.command(name='delete',
                       short_help="Delete resource tags from "
                                  "a specific plugin")
@cfy.argument('key', callback=cfy.parse_and_validate_label_to_delete)
@cfy.argument('plugin-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='plugin')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete_resource_tags(key, plugin_id, logger, client, tenant_name):
    """
    KEY: A resource tag's key to be deleted.
    """
    _delete_metadata(plugin_id, 'resource_tags', key, tenant_name,
                     client.plugins, logger)


def _list_metadata(plugin_id,
                   metadata_type,
                   tenant_name,
                   client,
                   logger):
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing %s of plugin %s...', metadata_type, plugin_id)
    metadata = client.get(plugin_id)[metadata_type]
    if not metadata:
        output('There are no {0} associated with the plugin {1}'
               .format(metadata_type, plugin_id))
    elif get_global_json_output():
        output(json.dumps(metadata, cls=CloudifyJSONEncoder))
    elif metadata_type.endswith('labels'):
        print_data(['key', 'values'],
                   get_printable_resource_labels(metadata),
                   '{0} labels'.format('Plugin'),
                   max_width=50)
    else:
        print_data(['key', 'value'],
                   [{'key': k, 'value': v} for k, v in metadata.items()],
                   '{0} labels'.format('Plugin'),
                   max_width=50)


def _add_metadata(plugin_id,
                  metadata_type,
                  metadata_list,
                  tenant_name,
                  client,
                  logger):
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Adding %s to plugin %s...', metadata_type, plugin_id)

    metadata = client.get(plugin_id)[metadata_type] or {}
    for added_metadata in metadata_list:
        for k, v in added_metadata.items():
            if k in metadata:
                if v not in metadata[k]:
                    metadata[k].append(v)
            else:
                metadata[k] = [v]
    _update_metadata(plugin_id, metadata_type, client,
                     **{metadata_type: metadata})
    logger.info('The %s of plugin %s were added: %s',
                metadata_type, plugin_id, metadata_list)


def _delete_metadata(plugin_id,
                     metadata_type,
                     metadata_list,
                     tenant_name,
                     client,
                     logger):
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Deleting %s from plugin %s...', metadata_type, plugin_id)

    metadata = client.get(plugin_id)[metadata_type]
    if not metadata:
        output('There are no {0} associated with the plugin {1}'
               .format(metadata_type, plugin_id))
        return
    for deleted_metadata in metadata_list:
        for k, v in deleted_metadata.items():
            if k in metadata:
                if v in metadata[k]:
                    metadata[k].remove(v)
                elif v is None:
                    del metadata[k]
    _update_metadata(plugin_id, metadata_type, client,
                     **{metadata_type: metadata})
    if metadata_type.endswith('labels'):
        logger.info('The %s of plugin %s were deleted: %s',
                    metadata_type, plugin_id, metadata_list)
    else:
        logger.info('The %s of plugin %s were deleted: %s',
                    metadata_type, plugin_id,
                    ", ".join(k for m in metadata_list for k in m.keys()))


def _update_metadata(plugin_id,
                     metadata_type,
                     client,
                     **kwargs):
    plugin = client.update(plugin_id, **kwargs)
    return plugin[metadata_type]
