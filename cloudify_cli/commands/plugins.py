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
import time

import click
import wagon

from cloudify.models_states import PluginInstallationState

from cloudify_cli import execution_events_fetcher
from cloudify_cli.logger import get_events_logger
from cloudify_cli.exceptions import (
    SuppressedCloudifyCliError, CloudifyCliError, CloudifyValidationError,
)

from cloudify_rest_client.constants import VISIBILITY_EXCEPT_PRIVATE
from cloudify_rest_client.exceptions import CloudifyClientError

from .. import utils
from ..logger import get_global_json_output
from ..table import print_data, print_single, print_details
from ..cli import helptexts, cfy
from ..utils import (prettify_client_error,
                     get_visibility,
                     validate_visibility)

PLUGIN_COLUMNS = ['id', 'package_name', 'package_version', 'installed on',
                  'distribution', 'distribution_release', 'uploaded_at',
                  'visibility', 'tenant_name', 'created_by',
                  'yaml_url_path']
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
    client.license.check()
    # Test whether the path is a valid URL. If it is, no point in doing local
    # validations - it will be validated on the server side anyway
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Creating plugin zip archive..')
    wagon_path = utils.get_local_path(plugin_path, create_temp=True)
    yaml_path = utils.get_local_path(yaml_path, create_temp=True)
    zip_files = [wagon_path, yaml_path]
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
        logger.info("Plugin uploaded. Plugin's id is {0}".format(plugin.id))
    finally:
        for f in zip_files:
            os.remove(f)
        os.remove(zip_path)


@plugins.command(name='bundle-upload',
                 short_help='Upload a bundle of plugins [manager only]')
@cfy.options.plugins_bundle_path
@cfy.pass_client()
@cfy.pass_logger
def upload_caravan(client, logger, path):
    client.license.check()
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
    logger.info('Retrieving plugin {0}...'.format(plugin_id))
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
    logger.info('Showing {0} of {1} plugins'.format(len(plugins_list),
                                                    total))


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

    utils.explicit_tenant_name_message(tenant_name, logger)
    if blueprint_id:
        _update_a_blueprint(blueprint_id, plugin_names,
                            to_latest, all_to_latest, to_minor, all_to_minor,
                            include_logs, json_output, logger,
                            client, force, auto_correct_types,
                            reevaluate_active_statuses)
    elif all_blueprints:
        update_results = {'successful': [], 'failed': []}
        pagination_offset = 0
        while True:
            blueprints = client.blueprints.list(
                sort='created_at',
                _all_tenants=all_tenants,
                _offset=pagination_offset,
            )
            for blueprint in blueprints:
                if blueprint.id in except_blueprints:
                    continue
                try:
                    _update_a_blueprint(blueprint.id, plugin_names,
                                        to_latest, all_to_latest,
                                        to_minor, all_to_minor,
                                        include_logs, json_output, logger,
                                        client, force, auto_correct_types,
                                        reevaluate_active_statuses)
                    update_results['successful'].append(blueprint.id)
                except CloudifyClientError as ex:
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


def _update_a_blueprint(blueprint_id,
                        plugin_names,
                        to_latest,
                        all_to_latest,
                        to_minor,
                        all_to_minor,
                        include_logs,
                        json_output,
                        logger,
                        client,
                        force,
                        auto_correct_types,
                        reevaluate_active_statuses):
    logger.info('Updating the plugins of the deployments of the blueprint '
                '{}'.format(blueprint_id))
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
