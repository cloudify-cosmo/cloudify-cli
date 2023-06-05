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
import uuid
import json
from datetime import datetime
from io import StringIO

import click

from cloudify_rest_client.constants import VISIBILITY_EXCEPT_PRIVATE
from cloudify_rest_client.exceptions import (
    DeploymentPluginNotFound,
    UnknownDeploymentInputError,
    UnknownDeploymentSecretError,
    MissingRequiredDeploymentInputError,
    UnsupportedDeploymentGetSecretError,
    CloudifyClientError
)
from cloudify.utils import parse_utc_datetime

from cloudify_cli.local import load_env
from cloudify_cli.table import (
    print_data,
    print_single,
    print_details,
    print_list
)
from cloudify_cli.cli import cfy, helptexts
from cloudify_cli.logger import (
    get_events_logger,
    get_global_json_output,
    output,
    get_global_extended_view
)
from cloudify_cli import env, execution_events_fetcher, filters_utils, utils
from cloudify_cli.constants import DEFAULT_BLUEPRINT_PATH, DELETE_DEP
from cloudify_cli.exceptions import (
    CloudifyCliError,
    SuppressedCloudifyCliError,
    ExecutionTimeoutError)
from cloudify_cli.labels_utils import (
    add_labels,
    delete_labels,
    get_output_resource_labels,
    get_printable_resource_labels,
    list_labels,
    serialize_resource_labels)
from cloudify_cli.utils import (
    prettify_client_error,
    get_visibility,
    validate_visibility,
    get_deployment_environment_execution)
from cloudify_cli.commands.summary import (
    BASE_SUMMARY_FIELDS,
    structure_summary_results)


DEPLOYMENT_COLUMNS = [
    'id', 'display_name', 'blueprint_id', 'created_at', 'updated_at',
    'visibility', 'tenant_name', 'created_by', 'site_name', 'labels',
    'deployment_status', 'installation_status'
]
DEPLOYMENT_STATUS_LIST_COLUMNS = [
    'id', 'display_name', 'deployment_status', 'installation_status',
    'unavailable_instances', 'drifted_instances',
]
EXTENDED_DEPLOYMENT_COLUMNS = DEPLOYMENT_COLUMNS + [
    'sub_services_count', 'sub_services_status', 'sub_environments_count',
    'sub_environments_status', 'unavailable_instances', 'drifted_instances',
]
DEPLOYMENT_UPDATE_COLUMNS = [
    'id', 'deployment_id', 'tenant_name', 'state', 'execution_id',
    'created_at', 'visibility', 'old_blueprint_id', 'new_blueprint_id'
]
DEPLOYMENT_UPDATE_PREVIEW_COLUMNS = [
    'deployment_id', 'tenant_name', 'state', 'created_at', 'visibility',
    'old_blueprint_id', 'new_blueprint_id'
]
DEPLOYMENT_MODIFICATION_COLUMNS = [
    'id', 'workflow_id', 'execution_id', 'status', 'tenant_name',
    'created_at', 'visibility',
]
NON_PREVIEW_COLUMNS = ['id', 'execution_id']
STEPS_COLUMNS = ['entity_type', 'entity_id', 'action']
DEPENDENCIES_COLUMNS = ['deployment', 'dependency_type', 'dependent_node',
                        'tenant']
DEP_GROUP_COLUMNS = [
    'id', 'deployments', 'description', 'default_blueprint_id'
]
TENANT_HELP_MESSAGE = 'The name of the tenant of the deployment'
DEPLOYMENTS_SUMMARY_FIELDS = (['blueprint_id', 'site_name'] +
                              BASE_SUMMARY_FIELDS)
SCHEDULES_SUMMARY_FIELDS = (['deployment_id', 'workflow_id'] +
                            BASE_SUMMARY_FIELDS)
# for human-redable outputs, those fields are formatted separately. In
# machine-readable (json) output, they are just part of the output
MACHINE_READABLE_UPDATE_PREVIEW_COLUMNS = [
    'old_inputs', 'new_inputs', 'steps', 'modified_entity_ids',
    'installed_nodes', 'uninstalled_nodes', 'reinstalled_nodes',
    'explicit_reinstall', 'recursive_dependencies', 'schedules_to_delete',
    'schedules_to_create', 'labels_to_create'
]
MACHINE_READABLE_MODIFICATION_COLUMNS = [
    'ended_at', 'node_instances', 'deployment_id', 'blueprint_id',
    'modified_nodes', 'resource_availability',
]
SCHEDULE_TABLE_COLUMNS = ['id', 'deployment_id', 'workflow_id', 'created_at',
                          'next_occurrence', 'since', 'until', 'stop_on_fail',
                          'enabled', 'visibility', 'tenant_name', 'created_by']


@cfy.group(name='deployments')
@cfy.options.common_options
def deployments():
    """Handle deployments on the Manager"""


def _print_single_update(
    deployment_update_dict,
    explicit_reinstall=None,
    preview=False,
    skip_install=False,
    skip_uninstall=False,
    skip_reinstall=False,
):
    if explicit_reinstall is None:
        explicit_reinstall = []
    if preview:
        columns = DEPLOYMENT_UPDATE_PREVIEW_COLUMNS
    else:
        columns = DEPLOYMENT_UPDATE_COLUMNS

    deployment_update_dict['explicit_reinstall'] = explicit_reinstall
    deployment_update_dict['installed_nodes'] = []
    deployment_update_dict['uninstalled_nodes'] = []
    deployment_update_dict['reinstalled_nodes'] = []
    for step in deployment_update_dict['steps']:
        entity = step['entity_id']
        if entity[0] != 'nodes':
            continue
        if step['action'] == 'add':
            deployment_update_dict['installed_nodes'].append(entity[1])
        elif step['action'] == 'remove':
            deployment_update_dict['uninstalled_nodes'].append(entity[1])
        elif step['action'] == 'modify':
            deployment_update_dict['reinstalled_nodes'].append(entity[1])
    raw_new_labels = deployment_update_dict.get('labels_to_create') or []
    new_labels = get_output_resource_labels(raw_new_labels)
    deployment_update_dict['labels_to_create'] = new_labels

    if get_global_json_output():
        columns += MACHINE_READABLE_UPDATE_PREVIEW_COLUMNS

    print_single(columns,
                 deployment_update_dict,
                 'Deployment Update:',
                 max_width=50)

    if not get_global_json_output():
        # beautify steps entity IDs for display
        for step in deployment_update_dict['steps']:
            step['entity_id'] = ': '.join(step['entity_id'])

        skip_msg = ' (will be skipped)'
        print_details(deployment_update_dict['old_inputs'] or {},
                      'Old inputs:')
        print_details(deployment_update_dict['new_inputs'] or {},
                      'New inputs:')
        print_data(STEPS_COLUMNS,
                   deployment_update_dict['steps'] or {},
                   'Steps:')
        print_list(
            deployment_update_dict['installed_nodes'] or [],
            'Installed nodes{0}:'.format(skip_msg if skip_install else '')
        )
        print_list(
            deployment_update_dict['uninstalled_nodes'] or [],
            'Uninstalled nodes{0}:'.format(skip_msg if skip_uninstall else '')
        )
        print_list(deployment_update_dict['reinstalled_nodes'] or [],
                   'Automatically detected nodes to reinstall{0}:'
                   .format(skip_msg if skip_reinstall else ''))
        print_list(explicit_reinstall, 'Expicitly given nodes to reinstall:')
        print_data(DEPENDENCIES_COLUMNS,
                   deployment_update_dict['recursive_dependencies'] or {},
                   'Affected (recursively) dependent deployments:')

        output('Will delete the following schedules: {}'.format(', '.join(
            deployment_update_dict.get('schedules_to_delete') or [])))
        print_data(
            ['id', 'workflow', 'since', 'until', 'recurrence',
             'count', 'weekdays'],
            deployment_update_dict.get('schedules_to_create') or [],
            'Then, will create the following schedules: ')
        print_data(['key', 'values'],
                   get_printable_resource_labels(new_labels),
                   'The following labels will be created: ')


def deployments_list_base(
    ctx,
    blueprint_id,
    group_id,
    filter_id,
    filter_rules,
    sort_by,
    descending,
    all_tenants,
    search,
    search_name,
    dependencies_of,
    pagination_offset,
    pagination_size,
    logger,
    client,
    tenant_name,
):
    """Base function for deployment listing.

    list and status-list delegate to this, so that they can have a single
    implementation only differing by columns shown.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    if blueprint_id:
        logger.info('Listing deployments for blueprint %s...', blueprint_id)
    else:
        logger.info('Listing all deployments...')

    deployments = client.deployments.list(sort=sort_by,
                                          is_descending=descending,
                                          filter_rules=filter_rules,
                                          filter_id=filter_id,
                                          _all_tenants=all_tenants,
                                          _search=search,
                                          _offset=pagination_offset,
                                          _size=pagination_size,
                                          _group_id=group_id,
                                          blueprint_id=blueprint_id,
                                          _search_name=search_name,
                                          _dependencies_of=dependencies_of)
    serialize_resource_labels(deployments)
    total = deployments.metadata.pagination.total

    if ctx.command.name == 'status-list':
        columns = DEPLOYMENT_STATUS_LIST_COLUMNS
    elif get_global_extended_view() or get_global_json_output():
        columns = EXTENDED_DEPLOYMENT_COLUMNS
    else:
        columns = DEPLOYMENT_COLUMNS
    print_data(columns, deployments, 'Deployments:')

    filtered = None
    if filter_rules or filter_id:
        filtered = deployments.metadata.get('filtered')
    if filtered:
        logger.info('Showing %d of %d deployments (%d hidden by filter)',
                    len(deployments), total, filtered)
    else:
        logger.info('Showing %d of %d deployments', len(deployments), total)


# to have identical behaviour for both list and status-list, apply the same
# decorators to both. We'll have two "stub" functions representing those
# commands, and both delegate to the same base.
deployments_list_decorators = [
    cfy.options.blueprint_id(
        help='Show deployments created from this blueprint'),
    click.option(
        '--group-id', '-g',
        help='Show deployments belonging to this group'),
    cfy.options.filter_id,
    cfy.options.deployment_filter_rules,
    cfy.options.sort_by(),
    cfy.options.descending,
    cfy.options.tenant_name_for_list(
        required=False, resource_name_for_help='deployment'),
    cfy.options.all_tenants,
    cfy.options.search,
    cfy.options.search_name,
    cfy.options.dependencies_of,
    cfy.options.pagination_offset,
    cfy.options.pagination_size,
    cfy.options.common_options,
    cfy.assert_manager_active(),
    cfy.pass_client(),
    cfy.pass_logger,
    cfy.pass_context,
    cfy.options.extended_view,
]


def manager_list(*args, **kwargs):
    """List deployments

    If `--blueprint-id` is provided, list deployments for that blueprint.
    Otherwise, list deployments for all blueprints.
    """
    return deployments_list_base(*args, **kwargs)


def manager_status_list(*args, **kwargs):
    """Show deployment statuses

    Show a grid of various deployment statuses, allowing an at-a-glance
    insight of the state of the system.

    This command allows the same filtering that `cfy deployments list` does.
    """
    return deployments_list_base(*args, **kwargs)


for deco in deployments_list_decorators + [
    deployments.command(
        name='list', short_help='List deployments [manager only]'
    )
]:
    manager_list = deco(manager_list)


for deco in deployments_list_decorators + [
    deployments.command(
        name='status-list', short_help='Show deployment status [manager only]'
    )
]:
    manager_status_list = deco(manager_status_list)


@deployments.command(name='history',
                     short_help='List deployment updates [manager only]')
@cfy.options.deployment_id()
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='deployment update')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def manager_history(
    deployment_id,
    sort_by,
    descending,
    all_tenants,
    search,
    pagination_offset,
    pagination_size,
    logger,
    client,
    tenant_name,
):
    """Show deployment history by listing deployment updates

    If `--deployment-id` is provided, list deployment updates for that
    deployment. Otherwise, list deployment updates for all deployments.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    if deployment_id:
        logger.info('Listing deployment updates for deployment %s...',
                    deployment_id)
    else:
        logger.info('Listing all deployment updates...')

    deployment_updates = client.deployment_updates.list(
        sort=sort_by,
        is_descending=descending,
        _all_tenants=all_tenants,
        _search=search,
        _offset=pagination_offset,
        _size=pagination_size,
        deployment_id=deployment_id
    )
    total = deployment_updates.metadata.pagination.total
    print_data(
        DEPLOYMENT_UPDATE_COLUMNS, deployment_updates, 'Deployment updates:')
    logger.info('Showing %d of %s deployment updates',
                len(deployment_updates), total)


@deployments.command(
    name='get-update',
    short_help='Retrieve deployment update information [manager only]'
)
@cfy.argument('deployment-update-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='deployment update')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_get_update(deployment_update_id, logger, client, tenant_name):
    """Retrieve information for a specific deployment update

    `DEPLOYMENT_UPDATE_ID` is the id of the deployment update to get
    information on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving deployment update %s...', deployment_update_id)
    deployment_update_dict = client.deployment_updates.get(
        deployment_update_id)
    _print_single_update(deployment_update_dict)


@deployments.command(
    name='update', short_help='Update a deployment [manager only]')
@cfy.argument('deployment-id')
@cfy.options.blueprint_path(extra_message=' [UNSUPPORTED]')
@cfy.options.blueprint_filename(' [UNSUPPORTED]')
@cfy.options.blueprint_id()
@cfy.options.inputs
@cfy.options.reinstall_list
@cfy.options.workflow_id()
@cfy.options.skip_install
@cfy.options.skip_uninstall
@cfy.options.skip_reinstall
@cfy.options.skip_drift_check
@cfy.options.skip_heal
@cfy.options.force_reinstall
@cfy.options.ignore_failure
@cfy.options.install_first
@cfy.options.preview
@cfy.options.dont_update_plugins
@cfy.options.force(help=helptexts.FORCE_UPDATE)
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.visibility(mutually_exclusive_required=False)
@cfy.options.validate
@cfy.options.include_logs
@cfy.options.drift_only
@cfy.options.json_output
@cfy.options.common_options
@cfy.options.runtime_only_evaluation
@cfy.options.auto_correct_types
@cfy.options.reevaluate_active_statuses()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.pass_context
def manager_update(
    ctx,
    deployment_id,
    blueprint_path,
    inputs,
    reinstall_list,
    blueprint_filename,
    skip_install,
    skip_uninstall,
    skip_reinstall,
    skip_drift_check,
    skip_heal,
    force_reinstall,
    ignore_failure,
    install_first,
    preview,
    dont_update_plugins,
    workflow_id,
    force,
    include_logs,
    json_output,
    logger,
    client,
    tenant_name,
    blueprint_id,
    drift_only,
    visibility,
    validate,
    runtime_only_evaluation,
    auto_correct_types,
    reevaluate_active_statuses,
):
    """Update a specified deployment according to the specified blueprint.
    The blueprint can be supplied as an id of a blueprint that already exists
    in the system (recommended).
    The other way (not recommended) is to supply a blueprint to upload and
    use it to update the deployment [DEPRECATED]
    Note: using the deprecated way will upload the blueprint and then use it
    to update the deployment. So doing it twice with the same blueprint may
    fail because the blueprint id in the system will already exist. In this
    case it is better to use the first and recommended way, and simply pass
    the blueprint id.

    `DEPLOYMENT_ID` is the deployment's id to update.
    """
    if blueprint_path:
        raise CloudifyCliError(
            'Passing a path to blueprint for deployment update is no longer '
            'supported.  Use -b, --blueprint-id option instead to pass an ID '
            'of a blueprint that is already in the system, e.g. '
            '`cfy deployments update -b UPDATED_BLUEPRINT_ID DEPLOYMENT_ID`.')
    if not any([blueprint_id, blueprint_path, inputs, drift_only]):
        raise CloudifyCliError(
            'Must supply either a blueprint (by id of an existing blueprint, '
            'or a path to a new blueprint), or new inputs')
    if (not blueprint_path or not utils.is_archive(blueprint_path)) \
            and blueprint_filename not in (DEFAULT_BLUEPRINT_PATH,
                                           blueprint_path):
        raise CloudifyCliError(
            '--blueprint-filename param should be passed only when updating '
            'from an archive, so --blueprint-path must be passed as a path to '
            'a blueprint archive'
        )

    if tenant_name:
        logger.info('Explicitly using tenant `%s`', tenant_name)

    msg = 'Updating deployment {0}'.format(deployment_id)
    if inputs:
        msg += ' with new inputs'
    if blueprint_id:
        msg += ', using blueprint {0}'.format(blueprint_id)
    logger.info(msg)
    reinstall_list = reinstall_list or []
    deployment_update = \
        client.deployment_updates.update_with_existing_blueprint(
            deployment_id,
            blueprint_id,
            inputs,
            skip_install,
            skip_uninstall,
            skip_reinstall,
            skip_drift_check,
            skip_heal,
            force_reinstall,
            workflow_id,
            force,
            ignore_failure,
            install_first,
            reinstall_list,
            preview,
            not dont_update_plugins,
            runtime_only_evaluation=runtime_only_evaluation,
            auto_correct_types=auto_correct_types,
            reevaluate_active_statuses=reevaluate_active_statuses,
        )

    if preview:
        _print_single_update(
            deployment_update,
            explicit_reinstall=reinstall_list,
            preview=True,
            skip_install=skip_install,
            skip_uninstall=skip_uninstall,
            skip_reinstall=skip_reinstall,
        )
        return

    events_logger = get_events_logger(json_output)
    execution = execution_events_fetcher.wait_for_execution(
        client,
        client.executions.get(deployment_update.execution_id),
        events_handler=events_logger,
        include_logs=include_logs,
        timeout=None  # don't timeout ever
    )

    if execution.error:
        logger.info(
            "Execution of workflow '%s' for deployment '%s' failed [error=%s]",
            execution.workflow_id,
            execution.deployment_id,
            execution.error,
        )
        logger.info(
            'Failed updating deployment %s. Deployment update id: %s. '
            'Execution id: %s',
            deployment_id,
            deployment_update.id,
            execution.id,
        )
        raise SuppressedCloudifyCliError()
    else:
        logger.info(
            "Finished executing workflow '%s' on deployment '%s'",
            execution.workflow_id,
            execution.deployment_id,
        )
        logger.info(
            'Successfully updated deployment %s. '
            'Deployment update id: %s. Execution id: %s',
            deployment_id,
            deployment_update.id,
            execution.id,
        )


@deployments.command(name='create',
                     short_help='Create a deployment [manager only]')
@cfy.argument('deployment-id', required=False, callback=cfy.validate_name)
@cfy.options.blueprint_id(required=True)
@cfy.options.inputs
@cfy.options.private_resource
@cfy.options.visibility()
@cfy.options.site_name
@cfy.options.labels
@cfy.options.generate_id
@cfy.options.display_name
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.runtime_only_evaluation
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.skip_plugins_validation
def manager_create(
    blueprint_id,
    deployment_id,
    inputs,
    private_resource,
    visibility,
    site_name,
    labels,
    generate_id,
    display_name,
    logger,
    client,
    tenant_name,
    skip_plugins_validation,
    runtime_only_evaluation,
):
    """Create a deployment on the manager.

    `DEPLOYMENT_ID` is the id of the deployment you'd like to create.

    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Creating new deployment from blueprint %s...', blueprint_id)
    visibility = get_visibility(private_resource, visibility, logger)
    if deployment_id:
        if generate_id:
            raise CloudifyCliError('`--generate-id` cannot be provided if a '
                                   'deployment ID is specified')
    else:
        if generate_id:
            deployment_id = str(uuid.uuid4())
        else:
            deployment_id = blueprint_id

    display_name = display_name or deployment_id

    try:
        deployment = client.deployments.create(
            blueprint_id,
            deployment_id,
            inputs=inputs,
            visibility=visibility,
            skip_plugins_validation=skip_plugins_validation,
            site_name=site_name,
            runtime_only_evaluation=runtime_only_evaluation,
            labels=labels,
            display_name=display_name
        )
    except (MissingRequiredDeploymentInputError,
            UnknownDeploymentInputError) as e:
        logger.error('Unable to create deployment: %s', e)
        raise SuppressedCloudifyCliError(str(e))
    except DeploymentPluginNotFound as e:
        logger.info(
            "Unable to create deployment. Not all "
            "deployment plugins are installed on the Manager."
        )
        logger.info(
            "* Use 'cfy plugins upload' to upload the missing plugins"
            " to the Manager, or use 'cfy deployments create' with "
            "the '--skip-plugins-validation' flag to skip this validation."
        )
        raise CloudifyCliError(str(e))
    except (UnknownDeploymentSecretError,
            UnsupportedDeploymentGetSecretError) as e:
        logger.info('Unable to create deployment due to invalid secret')
        raise CloudifyCliError(str(e))

    logger.info("Deployment `%s` created. The deployment's id is %s",
                deployment.display_name, deployment.id)


@deployments.command(name='delete',
                     short_help='Delete a deployment [manager only]')
@cfy.argument('deployment-id')
@cfy.options.force(help=helptexts.FORCE_DELETE_DEPLOYMENT)
@cfy.options.common_options
@cfy.options.with_logs
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.recursive_delete
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_delete(
    deployment_id,
    force,
    with_logs,
    recursive,
    logger,
    client,
    tenant_name,
):
    """Delete a deployment from the manager

    `DEPLOYMENT_ID` is the id of the deployment to delete.
    """

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Trying to delete deployment %s...', deployment_id)
    client.deployments.delete(
        deployment_id,
        force,
        with_logs=with_logs,
        recursive=recursive,
    )
    try:
        execution = get_deployment_environment_execution(
            client, deployment_id, DELETE_DEP)
        if execution:
            execution_events_fetcher.wait_for_execution(
                client, execution, logger=logger)

    except ExecutionTimeoutError:
        raise CloudifyCliError(
            'Timed out waiting for deployment `{0}` to be deleted. Please '
            'execute `cfy deployments list` to check whether the '
            'deployment has been deleted.'.format(deployment_id))

    except CloudifyClientError as e:
        # ignore 404 errors for the execution or deployment - it was already
        # deleted before we were able to follow it
        if 'not found' not in str(e):
            raise

    except RuntimeError as e:
        # ignore the failure to get the execution - it was already deleted
        # before we were able to follow it
        if 'Failed to get' not in str(e):
            raise

    logger.info("Deployment deleted")


@deployments.command(name='outputs',
                     short_help='Show deployment outputs [manager only]')
@cfy.argument('deployment-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_outputs(deployment_id, logger, client, tenant_name):
    """Retrieve outputs for a specific deployment

    `DEPLOYMENT_ID` is the id of the deployment to print outputs for.
    """
    _present_outputs_or_capabilities(
        'outputs',
        deployment_id,
        tenant_name,
        logger,
        client
    )


@deployments.command(name='capabilities',
                     short_help='Show deployment capabilities [manager only]')
@cfy.argument('deployment-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_capabilities(deployment_id, logger, client, tenant_name):
    """Retrieve capabilities for a specific deployment

    `DEPLOYMENT_ID` is the id of the deployment to print capabilities for.
    """
    _present_outputs_or_capabilities(
        'capabilities',
        deployment_id,
        tenant_name,
        logger,
        client
    )


def _present_outputs_or_capabilities(
        resource, deployment_id, tenant_name, logger, client
):
    # resource is either "outputs" or "capabilities"

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving %s for deployment %s...', resource, deployment_id)
    dep = client.deployments.get(deployment_id, _include=[resource])
    definitions = getattr(dep, resource)
    client_api = getattr(client.deployments, resource)
    response = client_api.get(deployment_id)
    values_dict = getattr(response, resource)
    if get_global_json_output():
        values = {out: {
            'value': val,
            'description': definitions[out].get('description')
        } for out, val in values_dict.items()}
        print_details(values, 'Deployment {0}:'.format(resource))
    else:
        values = StringIO()
        for elem_name, elem in values_dict.items():
            values.write(' - "{0}":{1}'.format(elem_name, os.linesep))
            description = definitions[elem_name].get('description', '')
            values.write('     Description: {0}{1}'.format(description,
                                                           os.linesep))
            values.write(
                '     Value: {0}{1}'.format(elem, os.linesep))
        logger.info(values.getvalue())


@deployments.command(name='inputs',
                     short_help='Show deployment inputs [manager only]')
@cfy.argument('deployment-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_inputs(deployment_id, logger, client, tenant_name):
    """Retrieve inputs for a specific deployment

    `DEPLOYMENT_ID` is the id of the deployment to print inputs for.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving inputs for deployment %s...', deployment_id)
    dep = client.deployments.get(deployment_id, _include=['inputs'])
    if get_global_json_output():
        print_details(dep.inputs, 'Deployment inputs:')
    else:
        inputs_ = StringIO()
        for input_name, input in dep.inputs.items():
            inputs_.write(' - "{0}":{1}'.format(input_name, os.linesep))
            inputs_.write('     Value: {0}{1}'.format(input, os.linesep))
        logger.info(inputs_.getvalue())


@deployments.command(
    name='set-visibility',
    short_help="Set the deployment's visibility [manager only]"
)
@cfy.argument('deployment-id')
@cfy.options.visibility(required=True, valid_values=VISIBILITY_EXCEPT_PRIVATE)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def manager_set_visibility(deployment_id, visibility, logger, client):
    """Set the deployment's visibility to tenant

    `DEPLOYMENT_ID` is the id of the deployment to update
    """
    validate_visibility(visibility, valid_values=VISIBILITY_EXCEPT_PRIVATE)
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        client.deployments.set_visibility(deployment_id, visibility)
        logger.info('Deployment `%s` was set to %s', deployment_id, visibility)


@deployments.command(name='summary',
                     short_help='Retrieve summary of deployment details '
                                '[manager only]',
                     help=helptexts.SUMMARY_HELP.format(
                         type='deployments',
                         example='deployment with the same blueprint ID',
                         fields='|'.join(DEPLOYMENTS_SUMMARY_FIELDS)))
@cfy.argument('target_field', type=cfy.SummaryArgs(DEPLOYMENTS_SUMMARY_FIELDS))
@cfy.argument('sub_field', type=cfy.SummaryArgs(DEPLOYMENTS_SUMMARY_FIELDS),
              default=None, required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.group_id_filter
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def summary(target_field, sub_field, group_id, logger, client, tenant_name,
            all_tenants):
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of deployments on field %s', target_field)

    summary = client.summary.deployments.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
        deployment_group_id=group_id,
    )

    columns, items = structure_summary_results(
        summary.items,
        target_field,
        sub_field,
        'deployments',
    )

    print_data(
        columns,
        items,
        'Deployment summary by {field}'.format(field=target_field),
    )


@deployments.command(name='set-site',
                     short_help="Set the deployment's site [manager only]")
@cfy.argument('deployment-id')
@cfy.options.site_name
@cfy.options.detach_site
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def manager_set_site(deployment_id, site_name, detach_site, client, logger):
    """Set the deployment's site

    `DEPLOYMENT_ID` is the id of the deployment to update
    """
    if not (site_name or detach_site):
        raise CloudifyCliError(
            'Must provide either a `--site-name` of a valid site or '
            '`--detach-site` (for detaching the current site of '
            'the given deployment)'
        )

    client.deployments.set_site(deployment_id,
                                site_name=site_name,
                                detach_site=detach_site)
    if detach_site:
        logger.info('The site of `%s` was detached', deployment_id)
    else:
        logger.info('The site of `%s` was set to %s', deployment_id, site_name)


@deployments.command(name='set-owner',
                     short_help="Change deployment's ownership")
@cfy.argument('deployment-id')
@cfy.options.new_username()
@cfy.options.tenant_name(required=False, resource_name_for_help='secret')
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_owner(deployment_id, username, tenant_name, logger, client):
    """Set a new owner for the deployment."""
    utils.explicit_tenant_name_message(tenant_name, logger)
    dep = client.deployments.set_attributes(deployment_id, creator=username)
    logger.info('Deployment `%s` is now owned by user `%s`.',
                deployment_id, dep.get('created_by'))


@deployments.group(name='labels',
                   short_help="Handle a deployment's labels")
@cfy.options.common_options
def labels():
    if not env.is_initialized():
        env.raise_uninitialized()


@labels.command(name='list',
                short_help="List the labels of a specific deployment")
@cfy.argument('deployment-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list_deployment_labels(deployment_id,
                           logger,
                           client,
                           tenant_name):
    list_labels(deployment_id, 'deployment', client.deployments,
                logger, tenant_name)


@labels.command(name='add',
                short_help="Add labels to a specific deployment")
@cfy.argument('labels-list',
              callback=cfy.parse_and_validate_labels)
@cfy.argument('deployment-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_deployment_labels(labels_list,
                          deployment_id,
                          logger,
                          client,
                          tenant_name):
    """
    LABELS_LIST: <key>:<value>,<key>:<value>.
    Any comma and colon in <value> must be escaped with '\\'.
    """
    add_labels(deployment_id, 'deployment', client.deployments, labels_list,
               logger, tenant_name)


@labels.command(name='delete',
                short_help="Delete labels from a specific deployment")
@cfy.argument('label', callback=cfy.parse_and_validate_label_to_delete)
@cfy.argument('deployment-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete_deployment_labels(label,
                             deployment_id,
                             logger,
                             client,
                             tenant_name):
    """
    LABEL: A mixed list of labels and keys, i.e.
    <key>:<value>,<key>,<key>:<value>. If <key> is provided,
    all labels associated with this key will be deleted from the deployment.
    Any comma and colon in <value> must be escaped with `\\`
    """
    delete_labels(deployment_id, 'deployment', client.deployments, label,
                  logger, tenant_name)


@deployments.group(name='modifications',
                   short_help="Handle the deployments' modifications")
@cfy.options.common_options
def modifications():
    if not env.is_initialized():
        env.raise_uninitialized()


@modifications.command(name='list',
                       short_help="List the deployments' modifications")
@cfy.argument('deployment-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def list_modifications(deployment_id,
                       pagination_offset,
                       pagination_size,
                       logger,
                       client,
                       tenant_name):
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing modifications of the deployment %s...', deployment_id)
    deployment_modifications = client.deployment_modifications.list(
        deployment_id,
        _offset=pagination_offset,
        _size=pagination_size,
    )
    flattened = [dict(dm, **dm.context) if dm.get('context') else dm
                 for dm in deployment_modifications]
    total = deployment_modifications.metadata.pagination.total
    print_data(DEPLOYMENT_MODIFICATION_COLUMNS, flattened,
               'Deployment modifications:')
    logger.info('Showing %d of %d deployment modifications',
                len(deployment_modifications), total)


@modifications.command(name='get',
                       short_help="Retrieve information for a deployment's "
                                  "modification")
@cfy.argument('deployment-modification-id')
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='deployment modification')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get_modification(deployment_modification_id,
                     logger,
                     client,
                     tenant_name):
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving deployment modification %s...',
                deployment_modification_id)
    deployment_modification = client.deployment_modifications.get(
        deployment_modification_id)
    _print_deployment_modification(deployment_modification)


@modifications.command(name='rollback',
                       short_help="Rollback a deployment's modification")
@cfy.argument('deployment-modification-id')
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='deployment modification')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def rollback_modification(deployment_modification_id,
                          logger,
                          client,
                          tenant_name):
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Rolling back a deployment modification %s...',
                deployment_modification_id)
    deployment_modification = client.deployment_modifications.rollback(
        deployment_modification_id)
    _print_deployment_modification(deployment_modification)


def _print_deployment_modification(deployment_modification):
    def print_node_instance(genre, title, modified_only=False):
        if genre not in deployment_modification['node_instances'] or \
                not deployment_modification['node_instances'].get(genre):
            return
        print_list(
            [
                '{0} ({1})'.format(ni.get('id'), ni.get('node_id'))
                for ni in deployment_modification['node_instances'].get(genre)
                if not modified_only or ni.get('modification')
            ],
            title
        )

    columns = DEPLOYMENT_MODIFICATION_COLUMNS
    if get_global_json_output():
        columns += MACHINE_READABLE_MODIFICATION_COLUMNS
    dm = (dict(deployment_modification, **deployment_modification.context)
          if deployment_modification.context else deployment_modification)
    print_single(columns, dm, 'Deployment Modification:')
    if not get_global_json_output():
        if 'modified_nodes' in dm and dm['modified_nodes']:
            print_list(dm['modified_nodes'].keys(), 'Modified nodes:')
        if 'node_instances' in dm and dm['node_instances']:
            print_node_instance('before_modification',
                                '\nNode instances before modifications:')
            print_node_instance('before_rollback',
                                '\nNode instances before rollback:')
            print_node_instance('added_and_related',
                                '\nAdded node instances:',
                                modified_only=True)
            print_node_instance('removed_and_related',
                                '\nRemoved node instances:',
                                modified_only=True)


@deployments.group('groups')
def groups():
    """Manage deployment groups"""


def _format_group(g):
    """Format a restclient deployment group for display"""
    return {
        'id': g['id'],
        'description': g['description'],
        'default_blueprint_id': g['default_blueprint_id'],
        'deployments': str(len(g['deployment_ids']))
    }


@groups.command('list', short_help='List all deployment groups')
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def groups_list(client, logger):
    """List all deployment groups"""
    groups = [_format_group(g) for g in client.deployment_groups.list()]
    print_data(DEP_GROUP_COLUMNS, groups, 'Deployment groups:')


@groups.command('create', short_help='Create a new deployment group')
@click.argument('deployment-group-name')
@cfy.options.inputs
@cfy.options.group_default_blueprint
@cfy.options.group_description
@cfy.pass_client()
@cfy.pass_logger
def groups_create(deployment_group_name, inputs, default_blueprint,
                  description, client, logger):
    """Create a deployment group

    The provided inputs will be used as default inputs for new deployments
    created using `cfy deployments groups extend --count`.
    """
    client.deployment_groups.put(
        deployment_group_name,
        default_inputs=inputs,
        blueprint_id=default_blueprint,
        description=description
    )
    logger.info('Group %s created', deployment_group_name)


@groups.command('delete', short_help='Delete a deployment group')
@click.argument('deployment-group-name')
@cfy.options.delete_deployments
@cfy.options.with_logs
@cfy.options.recursive_delete
@cfy.options.force(help=helptexts.FORCE_DELETE_DEPLOYMENT)
@cfy.pass_client()
@cfy.pass_logger
def groups_delete(
    deployment_group_name,
    delete_deployments,
    force,
    with_logs,
    recursive,
    client,
    logger,
):
    """Delete a deployment group

    This deletes a deployment group, which by default only removes the
    grouping, the deployments in the group are still left intact.
    To delete all deployments, pass `--delete-deployments`.
    """
    client.deployment_groups.delete(
        deployment_group_name,
        delete_deployments=delete_deployments,
        force=force,
        with_logs=with_logs,
        recursive=recursive,
    )
    logger.info('Group %s deleted', deployment_group_name)


@groups.command('update', short_help='Update a deployment group')
@click.argument('deployment-group-name')
@cfy.options.inputs
@cfy.options.group_default_blueprint
@cfy.options.group_description
@cfy.pass_client()
@cfy.pass_logger
def groups_update(deployment_group_name, inputs, default_blueprint,
                  description, client, logger):
    """Update a deployment group

    This changes the group's attributes; for updating deployments belonging
    to this group, see `update-deployments`.
    """
    client.deployment_groups.put(
        deployment_group_name,
        default_inputs=inputs,
        blueprint_id=default_blueprint,
        description=description
    )
    logger.info('Group %s updated', deployment_group_name)


@groups.command('extend', short_help='Add deployments to a group')
@click.argument('deployment-group-name')
@cfy.options.group_deployment_id
@cfy.options.group_count
@cfy.options.deployment_group_filter_id
@cfy.options.deployment_filter_rules
@cfy.options.deployment_group_deployments_from_group
@cfy.options.into_environments_group
@cfy.pass_client()
@cfy.pass_logger
def groups_extend(deployment_group_name, deployment_id, count, filter_id,
                  filter_rules, from_group, environments_group,
                  client, logger):
    """Add deployments to an existing group

    This adds deployments from a filter, or from another group, or creates
    new deployments, using this group's default blueprint and inputs.
    """
    new_deployments = []
    if environments_group:
        for deployment in client.deployments.list(
                deployment_group_id=environments_group):
            if deployment.is_environment():
                new_deployments.append({
                    'id': '{uuid}',
                    'display_name': '{blueprint_id}-{uuid}',
                    'labels': [{'csys-obj-parent': deployment.id}],
                })
    group = client.deployment_groups.add_deployments(
        deployment_group_name,
        filter_id=filter_id,
        filter_rules=filter_rules,
        count=count,
        deployment_ids=deployment_id or None,
        deployments_from_group=from_group,
        new_deployments=new_deployments or None,
    )
    logger.info(
        'Group %s updated. It now contains %d deployments',
        deployment_group_name, len(group.deployment_ids)
    )


@groups.command('shrink', short_help='Remove deployments from a group')
@click.argument('deployment-group-name')
@cfy.options.group_deployment_id
@cfy.options.deployment_group_filter_id
@cfy.options.deployment_filter_rules
@cfy.options.deployment_group_deployments_from_group
@cfy.pass_client()
@cfy.pass_logger
def groups_shrink(deployment_group_name, deployment_id, filter_id,
                  filter_rules, from_group, client, logger):
    """Shrink a group, removing deployments from it"""
    group = client.deployment_groups.remove_deployments(
        deployment_group_name,
        deployment_id,
        filter_id=filter_id,
        filter_rules=filter_rules,
        deployments_from_group=from_group,
    )
    removed_what_message = []
    if deployment_id:
        removed_what_message.append(', '.join(deployment_id))
    if filter_id:
        removed_what_message.append('given by filter {0}'.format(filter_id))
    if from_group:
        removed_what_message.append(
            'belonging to the group {0}'.format(from_group))
    logger.info(
        'Unlinked deployments %s. Group %s now has %d deployments',
        '; '.join(removed_what_message), deployment_group_name,
        len(group.deployment_ids)
    )


@groups.group(name='labels', short_help="Handle a group's labels")
@cfy.options.common_options
def group_labels():
    if not env.is_initialized():
        env.raise_uninitialized()


@group_labels.command(name='list', short_help="List the labels of a group")
@click.argument('deployment-group-name')
@cfy.options.tenant_name(required=False, resource_name_for_help='group')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list_group_labels(deployment_group_name, logger, client, tenant_name):
    """List labels of a group"""
    list_labels(deployment_group_name, 'deployment group',
                client.deployment_groups, logger, tenant_name)


@group_labels.command(name='add', short_help="Add labels to a group")
@cfy.argument('labels-list', callback=cfy.parse_and_validate_labels)
@click.argument('deployment-group-name')
@cfy.options.tenant_name(required=False, resource_name_for_help='group')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_group_labels(labels_list, deployment_group_name,
                     logger, client, tenant_name):
    """Add labels to the deployment group.

    Dpeloyments added to this group will have the group labels added to them.
    LABELS_LIST: <key>:<value>,<key>:<value>
    """
    add_labels(deployment_group_name, 'deployment group',
               client.deployment_groups, labels_list, logger, tenant_name)


@group_labels.command(name='delete', short_help="Delete labels from a group")
@cfy.argument('label', callback=cfy.parse_and_validate_label_to_delete)
@click.argument('deployment-group-name')
@cfy.options.tenant_name(required=False, resource_name_for_help='group')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete_group_labels(label, deployment_group_name,
                        logger, client, tenant_name):
    """Remove a label from the deployment group.

    Deployments added to this group will no longer have the label
    added to them.

    LABEL: Can be either <key>:<value> or <key>. If <key> is provided,
    all labels associated with this key will be deleted from the group.
    """
    delete_labels(deployment_group_name, 'deployment group',
                  client.deployment_groups, label, logger, tenant_name)


@groups.command(name='update-deployments',
                short_help='Update all deployments in the group')
@cfy.argument('group-id')
@cfy.options.blueprint_id()
@cfy.options.inputs
@cfy.options.reinstall_list
@cfy.options.workflow_id()
@cfy.options.skip_install
@cfy.options.skip_uninstall
@cfy.options.skip_reinstall
@cfy.options.skip_drift_check
@cfy.options.skip_heal
@cfy.options.force_reinstall
@cfy.options.ignore_failure
@cfy.options.install_first
@cfy.options.dont_update_plugins
@cfy.options.force(help=helptexts.FORCE_UPDATE)
@cfy.options.tenant_name(required=False, resource_name_for_help='group')
@cfy.options.common_options
@cfy.options.runtime_only_evaluation
@cfy.options.auto_correct_types
@cfy.options.reevaluate_active_statuses()
@cfy.options.execution_group_concurrency
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.pass_context
def groups_update_deployments(ctx, group_id, logger, client, tenant_name,
                              concurrency, **kwargs):
    """Update all deployments in the given group.

    If updating with a new blueprint, the blueprint must already be
    uploaded.
    Arguments have the same meaning as in single-deployment update,
    except that preview is not supported.
    This creates an execution-group with an update workflow for each
    deployment in the group.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Starting update of all deployments in group %s', group_id)
    if 'blueprint_id' in kwargs:
        # check that the blueprint exists ahead of time, throw otherwise
        client.blueprints.get(kwargs['blueprint_id'])
    if 'dont_update_plugins' in kwargs:
        kwargs['update_plugins'] = not kwargs.pop('dont_update_plugins')
    execution_group = client.execution_groups.start(
        deployment_group_id=group_id,
        workflow_id='csys_update_deployment',
        default_parameters=kwargs,
        concurrency=concurrency,
    )
    logger.info('For update status, follow this execution group: %s',
                execution_group.id)


@deployments.group(name='schedule')
@cfy.options.common_options
def schedule():
    """Handle deployments' execution scheduling [manager only]"""


@schedule.command(name='create',
                  short_help='Schedule a deployment\'s workflow execution')
@cfy.argument('deployment-id')
@cfy.argument('workflow-id')
@cfy.options.schedule_name
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.force(help=helptexts.FORCE_CONCURRENT_EXECUTION)
@cfy.options.dry_run
@cfy.options.wait_after_fail
@cfy.options.common_options
@cfy.options.since(required=True)
@cfy.options.until(required=False)
@cfy.options.tz
@cfy.options.recurrence
@cfy.options.count
@cfy.options.weekdays
@cfy.options.rrule
@cfy.options.slip
@cfy.options.stop_on_fail
@cfy.assert_manager_active()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.pass_client()
@cfy.pass_logger
def schedule_create(
    deployment_id,
    workflow_id,
    schedule_name,
    since,
    until,
    tz,
    parameters,
    allow_custom_parameters,
    force,
    dry_run,
    wait_after_fail,
    recurrence,
    count,
    weekdays,
    rrule,
    slip,
    stop_on_fail,
    tenant_name,
    client,
    logger,
):
    """
    Schedule the execution of a workflow on a given deployment

    `DEPLOYMENT_ID` is the ID of the deployment for which to create the
        schedule.
    `WORKFLOW_ID` is the ID of the workflow the schedule will run.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    if not schedule_name:
        schedule_name = workflow_id
    logger.info(
        'Scheduling the execution of workflow `%s` on deployment `%s`. '
        'Schedule name: %s', workflow_id, deployment_id, schedule_name)

    # calculate naive UTC datetimes from time expressions in since and until
    since_datetime = parse_utc_datetime(since, tz)
    until_datetime = parse_utc_datetime(until, tz)

    client.execution_schedules.create(
        schedule_name,
        deployment_id,
        workflow_id,
        execution_arguments={
            'allow_custom_parameters': allow_custom_parameters,
            'force': force,
            'dry_run': dry_run,
            'wait_after_fail': wait_after_fail,
        },
        parameters=parameters,
        since=since_datetime,
        until=until_datetime,
        recurrence=recurrence,
        count=count,
        weekdays=weekdays,
        rrule=rrule,
        slip=slip,
        stop_on_fail=stop_on_fail)

    logger.info('Deployment schedule created successfully')


@schedule.command(name='update',
                  short_help='Update a deployment schedule')
@cfy.argument('deployment-id')
@cfy.argument('schedule-id')
@cfy.options.common_options
@cfy.options.since(required=False)
@cfy.options.until(required=False)
@cfy.options.tz
@cfy.options.recurrence
@cfy.options.count
@cfy.options.weekdays
@cfy.options.rrule
@cfy.options.slip
@click.option(
    '--stop-on-fail/--continue-on-fail',
    required=False,
    help=helptexts.SCHEDULE_STOP_ON_FAIL
)
@cfy.assert_manager_active()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.pass_client()
@cfy.pass_logger
def schedule_update(
    deployment_id,
    schedule_id,
    since,
    until,
    tz,
    recurrence,
    count,
    weekdays,
    rrule,
    slip,
    stop_on_fail,
    tenant_name,
    client,
    logger,
):
    """
    Update an existing schedule for a workflow execution

    `DEPLOYMENT_ID` is the ID of the deployment to which the schedule belongs.
    `SCHEDULE_ID` is the ID of the deployment schedule to update.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Updating schedule `%s` on deployment `%s`...',
                schedule_id, deployment_id)

    # calculate naive UTC datetimes from time expressions in since and until
    since_datetime = parse_utc_datetime(since, tz)
    until_datetime = parse_utc_datetime(until, tz)

    client.execution_schedules.update(
        schedule_id,
        deployment_id,
        since=since_datetime,
        until=until_datetime,
        recurrence=recurrence,
        count=count,
        weekdays=weekdays,
        rrule=rrule,
        slip=slip,
        stop_on_fail=stop_on_fail)

    logger.info('Deployment schedule updated successfully')


@schedule.command(name='disable',
                  short_help='Disable a deployment schedule')
@cfy.argument('deployment-id')
@cfy.argument('schedule-id')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.pass_client()
@cfy.pass_logger
def schedule_disable(deployment_id, schedule_id, tenant_name, client, logger):
    """
    Disable a schedule for a workflow execution

    `DEPLOYMENT_ID` is the ID of the deployment to which the schedule belongs.
    `SCHEDULE_ID` is the ID of the deployment schedule to disable.
    """
    dep_schedule = client.execution_schedules.get(schedule_id, deployment_id)
    if not dep_schedule.enabled:
        raise CloudifyCliError(
            'Schedule `{}` on deployment `{}` is already disabled'.format(
                schedule_id, deployment_id))
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Disabling schedule `%s` on deployment `%s`...',
                schedule_id, deployment_id)
    client.execution_schedules.update(
        schedule_id, deployment_id, enabled=False)
    logger.info('Deployment schedule disabled successfully')


@schedule.command(name='enable',
                  short_help='Enable a disabled deployment schedule')
@cfy.argument('deployment-id')
@cfy.argument('schedule-id')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.pass_client()
@cfy.pass_logger
def schedule_enable(deployment_id, schedule_id, tenant_name, client, logger):
    """
    Enable a previously-disabled schedule for a workflow execution

    `DEPLOYMENT_ID` is the ID of the deployment to which the schedule belongs.
    `SCHEDULE_ID` is the ID of the deployment schedule to enable.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    dep_schedule = client.execution_schedules.get(schedule_id, deployment_id)
    if dep_schedule.enabled:
        raise CloudifyCliError(
            'Schedule `{}` on deployment `{}` is already enabled'.format(
                schedule_id, deployment_id))
    logger.info('Enabling schedule `%s` on deployment `%s`...',
                schedule_id, deployment_id)
    client.execution_schedules.update(
        schedule_id, deployment_id, enabled=True)
    logger.info('Deployment schedule enabled successfully')


@schedule.command(name='delete',
                  short_help='Delete a deployment schedule')
@cfy.argument('deployment-id')
@cfy.argument('schedule-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='deployment schedule')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def schedule_delete(deployment_id, schedule_id, logger, client, tenant_name):
    """
    Delete a schedule for a workflow execution

    `DEPLOYMENT_ID` is the ID of the deployment to which the schedule belongs.
    `SCHEDULE_ID` is the ID of the deployment schedule to delete.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Deleting schedule `%s` on deployment `%s`...',
                schedule_id, deployment_id)
    client.execution_schedules.delete(schedule_id, deployment_id)
    logger.info('Deployment schedule deleted successfully')


@schedule.command(name='list',
                  short_help='List deployment schedules')
@cfy.argument('deployment-id', required=False)
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='deployment schedule')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.options.since(required=False,
                   help_lead='List only schedules which have occurrences '
                             'after this time')
@cfy.options.until(required=False,
                   help_lead='List only schedules which have occurrences '
                             'before this time')
@cfy.options.tz
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def schedule_list(
    deployment_id,
    sort_by,
    descending,
    tenant_name,
    all_tenants,
    search,
    pagination_offset,
    pagination_size,
    since,
    until,
    tz,
    logger,
    client,
):
    """
    List all deployment schedules on the manager. If DEPLOYMENT_ID is
    provided, list only schedules of this deployment.
    """
    # calculate naive UTC datetimes from time expressions in since and until
    since_datetime = parse_utc_datetime(since, tz)
    until_datetime = parse_utc_datetime(until, tz)

    if not sort_by:
        sort_by = 'next_occurrence'
    kwargs = {}
    if deployment_id:
        kwargs['deployment_id'] = deployment_id

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing deployment schedules...')
    schedules = client.execution_schedules.list(sort=sort_by,
                                                is_descending=descending,
                                                _all_tenants=all_tenants,
                                                _search=search,
                                                _offset=pagination_offset,
                                                _size=pagination_size,
                                                **kwargs)
    total = schedules.metadata.pagination.total
    if since_datetime or until_datetime:
        schedules = _list_schedules_in_time_range(schedules,
                                                  since_datetime,
                                                  until_datetime)
    print_data(SCHEDULE_TABLE_COLUMNS, schedules, 'Deployment schedules:')
    logger.info('Showing %s of %s deployment schedules', len(schedules), total)


@schedule.command(name='get',
                  short_help='Retrieve deployment schedule information')
@cfy.argument('deployment-id')
@cfy.argument('schedule-id')
@click.option(
    '--preview',
    required=False,
    type=int,
    help="Preview N next dates for the workflow execution to run."
)
@cfy.options.common_options
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='deployment schedule')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def schedule_get(
    deployment_id,
    schedule_id,
    preview,
    logger,
    client,
    tenant_name,
):
    """
    Retrieve information for a specific deployment schedule

    `DEPLOYMENT_ID` is the ID of the deployment to which the schedule belongs.
    `SCHEDULE_ID` is the ID of the deployment schedule for which to
        retrieve information.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving execution schedule %s', schedule_id)
    dep_schedule = client.execution_schedules.get(schedule_id, deployment_id)

    columns = SCHEDULE_TABLE_COLUMNS
    extra_columns = ['rule', 'execution_arguments', 'all_next_occurrences']
    additional_data = {k.replace('_', ' '): v for k, v in dep_schedule.items()
                       if k not in SCHEDULE_TABLE_COLUMNS + extra_columns}
    if get_global_json_output():
        columns += additional_data.keys() + extra_columns
    print_single(columns, dep_schedule, 'Execution schedule:', max_width=50)

    if not get_global_json_output():
        print_details(dep_schedule['rule'], 'Scheduling rule:')
        print_details(dep_schedule['execution_arguments'],
                      'Execution arguments:')

        if additional_data.get('latest execution status') == 'terminated':
            additional_data['latest execution status'] = 'completed'
        print_details(additional_data, 'Additional data:')

        if preview:
            if not dep_schedule.enabled:
                raise CloudifyCliError(
                    'Deployment schedule {} is disabled, no upcoming '
                    'occurrences'.format(schedule_id))
            next_occurrences = dep_schedule['all_next_occurrences']

            computed_msg = 'Computed {} upcoming ' \
                           'occurrences.'.format(len(next_occurrences))
            listing_msg = ''
            if len(next_occurrences) > preview:
                listing_msg = 'Listing first {}:'.format(preview)
            elif len(next_occurrences) > 0:
                listing_msg = 'Listing:'
            logger.info('%s %s', computed_msg, listing_msg)
            for i, date in enumerate(next_occurrences):
                if i == preview:
                    break
                logger.info('  {:<5d} {}'.format(i + 1, date))


@schedule.command(name='summary',
                  short_help='Retrieve summary of deployment schedule details '
                             '[manager only]')
@cfy.argument('target_field', type=click.Choice(SCHEDULES_SUMMARY_FIELDS))
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def schedule_summary(target_field, logger, client, tenant_name, all_tenants):
    """
    Retrieve summary of deployment schedules, e.g. a count of schedules with
    the same deployment ID.

    `TARGET_FIELD` is the field to summarize deployment schedules on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of deployment schedules on field %s',
                target_field)

    sched_summary = client.summary.execution_schedules.get(
        _target_field=target_field,
        _sub_field='recurrence',
        _all_tenants=all_tenants,
    )
    columns, items = structure_summary_results(
        sched_summary.items,
        target_field,
        'recurrence',
        'execution_schedules',
    )
    print_data(
        columns,
        items,
        'Deployment schedules summary by {field}'.format(field=target_field),
    )


def _list_schedules_in_time_range(schedules, since, until):
    listed_schedules = []
    for sched in schedules:
        occurs_within_range = False
        for occurrence in sched['all_next_occurrences']:
            occurrence_dt = datetime.strptime(occurrence, '%Y-%m-%d %H:%M:%S')
            if since and occurrence_dt < since:
                continue
            if until and occurrence_dt > until:
                continue
            occurs_within_range = True
            break
        if occurs_within_range:
            listed_schedules.append(sched)
    return listed_schedules


@deployments.group(name='filters',
                   short_help="Handle the deployments' filters")
@cfy.options.common_options
def filters():
    if not env.is_initialized():
        env.raise_uninitialized()


@filters.command(name='list',
                 short_help="List all filters associated with deployments")
@cfy.options.sort_by('id')
@cfy.options.descending
@cfy.options.common_options
@cfy.options.tenant_name_for_list(required=False,
                                  resource_name_for_help='filter')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list_deployments_filters(
    sort_by,
    descending,
    tenant_name,
    all_tenants,
    search,
    pagination_offset,
    pagination_size,
    logger,
    client,
):
    """List all deployments' filters"""
    filters_utils.list_filters('deployments',
                               sort_by,
                               descending,
                               tenant_name,
                               all_tenants,
                               search,
                               pagination_offset,
                               pagination_size,
                               logger,
                               client.deployments_filters)


@filters.command(name='create', short_help="Create a new deployments' filter")
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.deployment_filter_rules
@cfy.options.visibility(mutually_exclusive_required=False)
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def create_deployments_filter(
    filter_id,
    filter_rules,
    visibility,
    tenant_name,
    logger,
    client,
):
    """Create a new deployments' filter

    `FILTER-ID` is the new filter's ID
    """
    filters_utils.create_filter('deployments',
                                filter_id,
                                filter_rules,
                                visibility,
                                tenant_name,
                                logger,
                                client.deployments_filters)


@filters.command(name='get',
                 short_help="Get details for a single deployments' filter")
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def get_deployments_filter(filter_id, tenant_name, logger, client):
    """Get details for a single deployments' filter

    `FILTER-ID` is the filter's ID
    """
    filters_utils.get_filter('deployments',
                             filter_id,
                             tenant_name,
                             logger,
                             client.deployments_filters)


@filters.command(name='update',
                 short_help="Update an existing deployments' filter")
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.deployment_filter_rules
@cfy.options.update_visibility
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def update_deployments_filter(
    filter_id,
    filter_rules,
    visibility,
    tenant_name,
    logger,
    client,
):
    """Update an existing deployments' filter's filter rules or visibility

    `FILTER-ID` is the filter's ID
    """
    filters_utils.update_filter('deployments',
                                filter_id,
                                filter_rules,
                                visibility,
                                tenant_name,
                                logger,
                                client.deployments_filters)


@filters.command(name='delete', short_help="Delete a deployments' filter")
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete_deployments_filter(filter_id, tenant_name, logger, client):
    """Delete a deployments' filter

    `FILTER-ID` is the filter's ID
    """
    filters_utils.delete_filter('deployments',
                                filter_id,
                                tenant_name,
                                logger,
                                client.deployments_filters)


@cfy.group(name='deployments')
@cfy.options.common_options
def local_deployments():
    """Handle local deployments"""


@local_deployments.command(
    name='inputs', short_help='Show deployment inputs [locally]')
@cfy.options.common_options
@cfy.options.blueprint_id(required=True)
@cfy.pass_logger
def local_inputs(blueprint_id, logger):
    """Display inputs for the execution
    """
    env = load_env(blueprint_id)
    logger.info(json.dumps(env.plan['inputs'] or {}, sort_keys=True, indent=2))


@local_deployments.command(
    name='outputs', short_help='Show deployment outputs [locally]')
@cfy.options.common_options
@cfy.options.blueprint_id(required=True)
@cfy.pass_logger
def local_outputs(blueprint_id, logger):
    """Display outputs for the execution
    """
    env = load_env(blueprint_id)
    logger.info(json.dumps(env.outputs() or {}, sort_keys=True, indent=2))
