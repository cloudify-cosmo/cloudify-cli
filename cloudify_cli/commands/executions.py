########
# Copyright (c) 2014-2019 Cloudify Platform Ltd. All rights reserved
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
import time

import click
from cloudify_rest_client import exceptions

from cloudify_cli import local, utils
from cloudify_cli.cli import cfy, helptexts
from cloudify_cli.constants import (
    DEFAULT_UNINSTALL_WORKFLOW,
    CREATE_DEPLOYMENT)
from cloudify_cli.exceptions import (
    CloudifyCliError,
    ExecutionTimeoutError,
    SuppressedCloudifyCliError)
from cloudify_cli.execution_events_fetcher import (
    ExecutionEventsFetcher,
    wait_for_execution,
    wait_for_execution_group)
from cloudify_cli.logger import (
    get_events_logger,
    get_global_json_output,
    get_global_extended_view)
from cloudify_cli.table import print_data, print_single, print_details
from cloudify_cli.utils import get_deployment_environment_execution

from cloudify_cli.commands.summary import (
    BASE_SUMMARY_FIELDS,
    structure_summary_results)

_STATUS_CANCELING_MESSAGE = (
    'NOTE: Executions currently in a "canceling/force-canceling" status '
    'may take a while to change into "cancelled"')

BASE_EXECUTION_COLUMNS = ['id', 'workflow_id', 'status_display']
LOCAL_EXECUTION_COLUMNS = BASE_EXECUTION_COLUMNS + [
    'blueprint_id', 'started_at', 'ended_at', 'error']
FULL_EXECUTION_COLUMNS = BASE_EXECUTION_COLUMNS + [
    'is_dry_run', 'deployment_id', 'blueprint_id', 'created_at', 'ended_at',
    'error', 'visibility', 'tenant_name', 'created_by', 'started_at',
    'scheduled_for']
MINIMAL_EXECUTION_COLUMNS = BASE_EXECUTION_COLUMNS + [
    'is_dry_run', 'deployment_id', 'created_at', 'started_at', 'scheduled_for',
    'visibility', 'tenant_name', 'created_by']
EXECUTION_TABLE_LABELS = {'status_display': 'status'}
EXECUTIONS_SUMMARY_FIELDS = [
    'status',
    'blueprint_id',
    'deployment_id',
    'workflow_id',
] + BASE_SUMMARY_FIELDS


@cfy.group(name='executions')
@cfy.options.common_options
def executions():
    """Handle workflow executions"""


@executions.command(name='get',
                    short_help='Retrieve execution information [manager only]')
@cfy.argument('execution-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='execution')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def manager_get(execution_id, logger, client, tenant_name):
    """Retrieve information for a specific execution

    `EXECUTION_ID` is the execution to get information on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    try:
        logger.info('Retrieving execution {0}'.format(execution_id))
        execution = client.executions.get(execution_id)
    except exceptions.CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Execution {0} not found'.format(execution_id))

    columns = FULL_EXECUTION_COLUMNS
    if get_global_json_output():
        columns += ['parameters']
    max_width = None if get_global_extended_view() else 50
    print_single(columns, execution, 'Execution:', max_width=max_width,
                 labels=EXECUTION_TABLE_LABELS)

    if not get_global_json_output():
        print_details(execution.parameters, 'Execution Parameters:')
    if execution.status in (execution.CANCELLING, execution.FORCE_CANCELLING):
        logger.info(_STATUS_CANCELING_MESSAGE)
    logger.info('')


@executions.command(name='list', short_help='List deployment executions')
@cfy.options.deployment_id(required=False)
@cfy.options.include_system_workflows
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='execution')
@cfy.options.all_tenants
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def manager_list(
        deployment_id,
        include_system_workflows,
        sort_by,
        descending,
        all_tenants,
        pagination_offset,
        pagination_size,
        logger,
        client,
        tenant_name):
    """List executions

    If `DEPLOYMENT_ID` is provided, list executions for that deployment.
    Otherwise, list executions for all deployments.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    try:
        if deployment_id:
            logger.info('Listing executions for deployment {0}...'.format(
                deployment_id))
        else:
            logger.info('Listing all executions...')
        executions = client.executions.list(
            deployment_id=deployment_id,
            include_system_workflows=include_system_workflows,
            sort=sort_by,
            is_descending=descending,
            _all_tenants=all_tenants,
            _offset=pagination_offset,
            _size=pagination_size,
            _include=MINIMAL_EXECUTION_COLUMNS,
        )

    except exceptions.CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} does not exist'.format(
            deployment_id))

    print_data(MINIMAL_EXECUTION_COLUMNS, executions, 'Executions:',
               labels=EXECUTION_TABLE_LABELS)
    total = executions.metadata.pagination.total
    logger.info('Showing {0} of {1} executions'.format(len(executions), total))

    if any(execution.status in (
            execution.CANCELLING, execution.FORCE_CANCELLING)
            for execution in executions):
        logger.info(_STATUS_CANCELING_MESSAGE)


@executions.command(name='start', short_help='Execute a workflow')
@cfy.argument('workflow-id')
@cfy.options.deployment_id(required=True)
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.force(help=helptexts.FORCE_CONCURRENT_EXECUTION)
@cfy.options.timeout()
@cfy.options.include_logs
@cfy.options.json_output
@cfy.options.dry_run
@cfy.options.wait_after_fail
@cfy.options.worker_names
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='execution')
@cfy.options.schedule
@cfy.options.queue
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_start(workflow_id,
                  deployment_id,
                  parameters,
                  allow_custom_parameters,
                  force,
                  timeout,
                  include_logs,
                  json_output,
                  dry_run,
                  wait_after_fail,
                  queue,
                  schedule,
                  with_worker_names,
                  logger,
                  client,
                  tenant_name):
    """Execute a workflow on a given deployment

    `WORKFLOW_ID` is the id of the workflow to execute (e.g. `uninstall`)
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    events_logger = get_events_logger(json_output, with_worker_names)
    events_message = "* Run 'cfy events list {0}' to retrieve the " \
                     "execution's events/logs"
    original_timeout = timeout

    if schedule:
        logger.info(
            'Scheduling the execution of workflow `%s` on deployment `%s`. ',
            workflow_id, deployment_id)
    else:
        logger.info('Executing workflow `{0}` on deployment `{1}`'
                    ' [timeout={2} seconds]'.format(workflow_id,
                                                    deployment_id,
                                                    timeout))
    try:
        try:
            execution = client.executions.start(
                deployment_id,
                workflow_id,
                parameters=parameters,
                allow_custom_parameters=allow_custom_parameters,
                force=force,
                dry_run=dry_run,
                queue=queue,
                wait_after_fail=wait_after_fail,
                schedule=schedule)
        except (exceptions.DeploymentEnvironmentCreationInProgressError,
                exceptions.DeploymentEnvironmentCreationPendingError) as e:
            # wait for deployment environment creation workflow
            if isinstance(
                    e,
                    exceptions.DeploymentEnvironmentCreationPendingError):
                status = 'pending'
            else:
                status = 'in progress'

            logger.info('Deployment environment creation is {0}...'.format(
                status))
            logger.debug('Waiting for create_deployment_environment '
                         'workflow execution to finish...')
            now = time.time()
            wait_for_execution(client,
                               get_deployment_environment_execution(
                                   client, deployment_id, CREATE_DEPLOYMENT),
                               events_handler=events_logger,
                               include_logs=include_logs,
                               timeout=timeout)
            remaining_timeout = time.time() - now
            timeout -= remaining_timeout
            # try to execute user specified workflow
            execution = client.executions.start(
                deployment_id,
                workflow_id,
                parameters=parameters,
                allow_custom_parameters=allow_custom_parameters,
                force=force,
                dry_run=dry_run,
                queue=queue,
                wait_after_fail=wait_after_fail,
                schedule=schedule)

        if execution.status == 'queued':  # We don't need to wait for execution
            logger.info('Execution is being queued. It will automatically'
                        ' start when possible.')
            return
        if execution.status == 'scheduled':
            logger.info('Execution is scheduled for %s.\nYou can see the '
                        'execution schedule using `cfy deployments schedule '
                        'list`.', schedule)
            return
        execution = wait_for_execution(client,
                                       execution,
                                       events_handler=events_logger,
                                       include_logs=include_logs,
                                       timeout=timeout,
                                       logger=logger)
        if execution.error:
            logger.info('Execution of workflow {0} for deployment '
                        '{1} failed. [error={2}]'.format(
                            workflow_id,
                            deployment_id,
                            execution.error))
            logger.info(events_message.format(execution.id))
            if workflow_id == DEFAULT_UNINSTALL_WORKFLOW and not str(
                    parameters.get('ignore_failure')).lower() == 'true':

                logger.info(
                    "Note that, for the {0} workflow, you can use the 'ignore_failure' parameter "  # noqa
                    'to ignore operation failures and continue the execution '
                    "(for example: 'cfy executions start {0} -d {1} -p ignore_failure=true'). "  # noqa
                    "If your blueprint imports Cloudify's global definitions (types.yaml) "  # noqa
                    'of a version prior to 4.0, you will also need to include '
                    "'--allow-custom-parameters' in the command line."
                    .format(workflow_id, deployment_id))
            raise SuppressedCloudifyCliError()
        else:
            logger.info('Finished executing workflow {0} on deployment '
                        '{1}'.format(workflow_id, deployment_id))
            logger.info(events_message.format(execution.id))
    except ExecutionTimeoutError as e:
        logger.info(
            "Timed out waiting for workflow '{0}' of deployment '{1}' to "
            "end. The execution may still be running properly; however, "
            "the command-line utility was instructed to wait up to {3} "
            "seconds for its completion.\n\n"
            "* Run 'cfy executions list' to determine the execution's "
            "status.\n"
            "* Run 'cfy executions cancel {2}' to cancel"
            " the running workflow.".format(
                workflow_id, deployment_id, e.execution_id, original_timeout))

        events_tail_message = "* Run 'cfy events list --tail " \
                              "{0}' to retrieve the " \
                              "execution's events/logs"
        logger.info(events_tail_message.format(e.execution_id))
        raise SuppressedCloudifyCliError()


@executions.command(name='cancel',
                    short_help='Cancel a workflow execution [manager only]')
@cfy.argument('execution-id')
@cfy.options.common_options
@cfy.options.force(help=helptexts.FORCE_CANCEL_EXECUTION)
@cfy.options.kill()
@cfy.options.tenant_name(required=False, resource_name_for_help='execution')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_cancel(execution_id, force, kill, logger, client, tenant_name):
    """Cancel a workflow's execution

    `EXECUTION_ID` is the ID of the execution to cancel.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    if kill:
        message = 'Killing'
    elif force:
        message = 'Force-cancelling'
    else:
        message = 'Cancelling'
    logger.info('{0} execution {1}'.format(message, execution_id))
    client.executions.cancel(execution_id, force=force, kill=kill)
    logger.info(
        "A cancel request for execution {0} has been sent. "
        "To track the execution's status, use:\n"
        "cfy executions get {0}".format(execution_id))


@executions.command(name='resume',
                    short_help='Resume a workflow execution [manager only]')
@cfy.argument('execution-id')
@cfy.options.common_options
@cfy.options.reset_operations
@cfy.options.tenant_name(required=False, resource_name_for_help='execution')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_resume(execution_id, reset_operations, logger, client,
                   tenant_name):
    """Resume the execution of a workflow in a failed or cancelled state.

    `EXECUTION_ID` is the ID of the execution to resume.
    The workflow will run again, restoring the tasks graph from the storage,
    and retrying failed tasks when necessary.
    If reset-operations is passed, tasks that were started but didn't fail
    will be retried as well.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Resuming execution {0}'.format(execution_id))
    client.executions.resume(execution_id, force=reset_operations)
    logger.info(
        "A resume request for execution {0} has been sent. "
        "To track the execution's status, use:\n"
        "cfy executions get {0}".format(execution_id))


@executions.command(name='summary',
                    short_help='Retrieve summary of execution details '
                               '[manager only]',
                    help=helptexts.SUMMARY_HELP.format(
                        type='executions',
                        example='execution with the same deployment ID',
                        fields='|'.join(EXECUTIONS_SUMMARY_FIELDS)))
@cfy.argument('target_field', type=cfy.SummaryArgs(EXECUTIONS_SUMMARY_FIELDS))
@cfy.argument('sub_field', type=cfy.SummaryArgs(EXECUTIONS_SUMMARY_FIELDS),
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
    logger.info('Retrieving summary of executions on field {field}'.format(
        field=target_field))

    summary = client.summary.executions.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
        execution_group_id=group_id,
    )

    columns, items = structure_summary_results(
        summary.items,
        target_field,
        sub_field,
        'executions',
    )

    print_data(
        columns,
        items,
        'Execution summary by {field}'.format(field=target_field),
    )


@executions.command(name='delete',
                    short_help='Delete finished executions')
@cfy.options.common_options
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='executions')
@cfy.options.to_datetime(required=False,
                         mutually_exclusive_with=['before', 'keep_last'],
                         help="Executions that were created at this timestamp"
                              " or before will be deleted")
@cfy.options.before(required=False,
                    mutually_exclusive_with=['to_datetime', 'keep_last'],
                    help="Executions that were created this long ago or "
                         "earlier will be deleted (e.g. '2 weeks')")
@cfy.options.keep_last("executions",
                       required=False,
                       mutually_exclusive_with=['before', 'to_datetime'])
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def delete(logger, client, tenant_name, to_datetime, before, keep_last,
           all_tenants):
    """Delete executions from the executions list, by specifying a number of
    executions to keep, a number of days to keep executions for, or a date
    starting from which to keep executions.

    * Only deletes finished executions, i.e. completed, failed or cancelled.

    * Does not delete the latest deployment environment creation for each
    deployment."""
    if before:
        to_datetime = before

    utils.explicit_tenant_name_message(tenant_name, logger)
    deleted_executions_count = client.executions.delete(
        to_datetime=to_datetime, keep_last=keep_last, _all_tenants=all_tenants)
    deleted_executions_count = deleted_executions_count
    if deleted_executions_count:
        logger.info('\nDeleted %d executions', deleted_executions_count)
    else:
        logger.info('\nNo executions to delete')


@executions.group('graphs')
@cfy.options.common_options
def graphs():
    """Handle executions' tasks-graphs"""


@graphs.command('list')
@cfy.options.common_options
@cfy.argument('execution-id', required=True)
@click.option('--name', help='List graphs with this name')
@cfy.pass_logger
@cfy.pass_client()
def graphs_list(execution_id, name, client, logger):
    """List tasks-graphs for an execution"""
    tgs = client.tasks_graphs.list(execution_id=execution_id, name=name)
    print_data(['id', 'name', 'created_at'], tgs,
               'Tasks graphs of execution {0}:'.format(execution_id))


@executions.group('operations')
@cfy.options.common_options
def operations():
    """Handle executions' operations"""


@operations.command('get')
@cfy.options.common_options
@cfy.argument('operation-id', required=True)
@cfy.pass_logger
@cfy.pass_client()
def operations_get(operation_id, client, logger):
    """Display the details of an operation"""
    op = client.operations.get(operation_id)
    print_details(op, 'Operation {0}:'.format(operation_id))


@operations.command('list')
@cfy.options.common_options
@cfy.argument('execution-id', required=False)
@click.option('--graph-id', required=False,
              help='List operations of this graph '
                   '(exclusive with execution-id)')
@click.option('--show-internal', type=bool, is_flag=True, default=False,
              help='Also list internal operations')
@click.option('--state', required=False, help='List operations in this state')
@cfy.pass_logger
@cfy.pass_client()
def operations_list(execution_id, graph_id, state, show_internal,
                    client, logger):
    """List operations for an execution or a graph"""
    ops = client.operations.list(
        graph_id=graph_id,
        execution_id=execution_id,
        state=state,
        skip_internal=not show_internal,
    )
    print_data(
        ['id', 'name', 'type', 'state', 'manager_name', 'agent_name'],
        ops,
        'Operations'
    )


@executions.group('groups')
@cfy.options.common_options
def groups():
    """Manage execution groups"""


@groups.command('get',
                short_help='Retrieve execution group information')
@cfy.argument('execution_group_id')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def execution_groups_get(execution_group_id, client, logger):
    """Display execution group information

    This includes the source deployment group, and the workflow name.
    """

    group = client.execution_groups.get(execution_group_id)
    print_single(
        ['id', 'workflow_id', 'deployment_group_id'],
        group,
        'Execution group {0}:'.format(execution_group_id)
    )


def _format_group(g):
    return {
        'id': g['id'],
        'workflow_id': g['workflow_id'],
        'deployment_group': g['deployment_group_id'],
    }


@groups.command('list',
                short_help='List all execution groups')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def execution_groups_list(client, logger):
    """List all execution groups"""
    groups = [_format_group(g) for g in client.execution_groups.list()]
    print_data(
        ['id', 'workflow_id', 'deployment_group'],
        groups,
        'Execution groups:'
    )


@groups.command('details',
                short_help='Details of an execution group [manager only]')
@cfy.argument('execution_group_id')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def execution_groups_details(execution_group_id, client, logger):
    """Show execution group details"""
    group = client.execution_groups.get(execution_group_id)
    group.update({'#executions': len(group.get('execution_ids'))})
    print_single(['workflow_id', 'deployment_group_id', '#executions',
                  'created_at', 'status'],
                 group,
                 'Execution group {0}:'.format(execution_group_id))

    # Let's find out the total number of events
    events = client.events.list(
        execution_group_id=execution_group_id,
        include_logs=True, _size=1)
    events_total = events.metadata.get('pagination', {}).get('total')
    execution_events = ExecutionEventsFetcher(
            client,
            include_logs=True,
            execution_group_id=execution_group_id
    )
    events_logger = get_events_logger(json_output=False)
    pagination_size = 10 if events_total >= 10 else events_total
    print_details(None, 'Last {0} logs:'.format(pagination_size))
    execution_events.fetch_and_process_events_batch(
        events_handler=events_logger,
        offset=events_total - pagination_size,
        size=pagination_size)

    summary = client.summary.executions.get(
        _target_field='status',
        execution_group_id=execution_group_id,
    )
    print_details({s['status']: s['executions'] for s in summary},
                  '\nExecutions\' status summary:')
    logger.info('')


@groups.command('start',
                short_help='Execute a workflow on each deployment in a group')
@click.option('--deployment-group', '-g',
              help='The deployment group ID to run the workflow on')
@cfy.options.execution_group_concurrency
@click.argument('workflow-id')
@cfy.options.common_options
@cfy.options.parameters
@cfy.options.worker_names
@cfy.options.json_output
@cfy.options.force(help=helptexts.FORCE_CONCURRENT_EXECUTION)
@cfy.options.timeout()
@cfy.pass_client()
@cfy.pass_logger
def execution_groups_start(deployment_group, workflow_id, parameters,
                           json_output, force, timeout, concurrency,
                           with_worker_names, client, logger):
    """Start an execution group

    This starts an execution on every deployment in the given deployment
    group.
    """
    events_logger = get_events_logger(json_output, with_worker_names)
    group = client.execution_groups.start(
        deployment_group_id=deployment_group,
        workflow_id=workflow_id,
        default_parameters=parameters,
        force=force,
        concurrency=concurrency,
    )
    logger.info('Execution group %s started: running %s on '
                'deployment group %s [concurrency=%s]',
                group.id, group.workflow_id, group.deployment_group_id,
                group.concurrency)
    try:
        execution = wait_for_execution_group(client, group,
                                             events_handler=events_logger,
                                             include_logs=True,
                                             timeout=timeout,
                                             logger=logger)
        logger.info("Finished executing workflow {0} on deployment group "
                    "{1}.\n\n"
                    "* Run 'cfy events list -g {2}' to retrieve the "
                    "execution group's events/logs".format(
                        workflow_id, deployment_group, execution.id)
                    )

    except ExecutionTimeoutError as e:
        logger.info("Timed out waiting for workflow '{0}' on deployment group "
                    "'{1}' to end. The execution group may still be running, "
                    "however, the command-line utility was instructed to wait "
                    "up to {3} seconds for its completion.\n\n"
                    "* Run 'cfy executions groups cancel {2}' to cancel the "
                    "running workflow.\n"
                    "* Run 'cfy events list -g {2} --tail' to retrieve the "
                    "execution group's events/logs".format(
                        workflow_id, deployment_group, e.execution_id, timeout)
                    )
        raise SuppressedCloudifyCliError()


@groups.command('cancel', short_help='Cancel an execution group')
@cfy.argument('group-id')
@cfy.options.force(help=helptexts.FORCE_CANCEL_EXECUTION)
@cfy.options.kill()
@cfy.options.tenant_name(
    required=False, resource_name_for_help='execution group')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def execution_groups_cancel(group_id, force, kill,
                            client, logger, tenant_name):
    """Cancel an execution group

    This cancels all running executions in the group. Executions that already
    finished are unaffected.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    if kill:
        message = 'Killing'
    elif force:
        message = 'Force-cancelling'
    else:
        message = 'Cancelling'
    logger.info('%s execution group %s', message, group_id)
    client.execution_groups.cancel(group_id, force=force, kill=kill)
    logger.info("A cancel request for group %s has been sent", group_id)


@groups.command('resume', short_help='Resume an execution group')
@cfy.argument('group-id')
@cfy.options.reset_operations
@cfy.options.tenant_name(
    required=False, resource_name_for_help='execution group')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def execution_groups_resume(group_id, reset_operations,
                            client, logger, tenant_name):
    """Resume an execution group

    This resumes all failed executions in the group. Executions that already
    finished are unaffected.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Resuming execution group %s', group_id)
    client.execution_groups.resume(group_id, force=reset_operations)
    logger.info("A resume request for group %s has been sent", group_id)


@groups.command('set-success-group',
                short_help='Set a target group for successful deployments')
@cfy.argument('group-id')
@cfy.argument('success-group-id')
@cfy.options.tenant_name(
    required=False, resource_name_for_help='execution group')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def execution_groups_set_success(group_id, success_group_id,
                                 client, logger, tenant_name):
    """Set success target group for this execution-group.

    Deployments for which the execution succeeds, will be added to the
    success target deployments group.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    client.execution_groups.set_target_group(
        group_id, success_group=success_group_id)
    logger.info('Execution group %s: success target group set to %s',
                group_id, success_group_id)


@groups.command('set-failure-group',
                short_help='Set a target group for failed deployments')
@cfy.argument('group-id')
@cfy.argument('failure-group-id')
@cfy.options.tenant_name(
    required=False, resource_name_for_help='execution group')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def execution_groups_set_failure(group_id, failure_group_id,
                                 client, logger, tenant_name):
    """Set failure target group for this execution-group.

    Deployments for which the execution fails, will be added to the
    success target deployments group.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    client.execution_groups.set_target_group(
        group_id, failed_group=failure_group_id)
    logger.info('Execution group %s: failure target group set to %s',
                group_id, failure_group_id)


@groups.command('set-concurrency',
                short_help='Change the concurrency for a group')
@cfy.argument('group-id')
@cfy.argument('concurrency', type=int)
@cfy.options.tenant_name(
    required=False, resource_name_for_help='execution group')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def execution_groups_set_concurrency(
    group_id, concurrency, client, logger, tenant_name,
):
    """Change the concurrency setting of an execution group.

    When starting executions belonging to this group, the new concurrency
    setting will be used. Already-running executions are unaffected.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    client.execution_groups.set_concurrency(group_id, concurrency)
    logger.info('Execution group %s: concurrency set to %s',
                group_id, concurrency)


@cfy.group(name='executions')
@cfy.options.common_options
def local_executions():
    """Handle workflow executions"""


@local_executions.command(name='start', short_help='Execute a workflow')
@cfy.argument('workflow-id')
@cfy.options.blueprint_id(required=True)
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.task_retries()
@cfy.options.task_retry_interval()
@cfy.options.task_thread_pool_size()
@cfy.options.common_options
@cfy.pass_logger
def local_start(workflow_id,
                blueprint_id,
                parameters,
                allow_custom_parameters,
                task_retries,
                task_retry_interval,
                task_thread_pool_size,
                logger):
    """Execute a workflow

    `WORKFLOW_ID` is the id of the workflow to execute (e.g. `uninstall`)
    """
    env = local.load_env(blueprint_id)
    result = env.execute(workflow=workflow_id,
                         parameters=parameters,
                         allow_custom_parameters=allow_custom_parameters,
                         task_retries=task_retries,
                         task_retry_interval=task_retry_interval,
                         task_thread_pool_size=task_thread_pool_size)
    if result is not None:
        logger.info(json.dumps(result, sort_keys=True, indent=2))


@local_executions.command(name='list', short_help='List deployment executions')
@cfy.options.blueprint_id(required=True)
@cfy.options.common_options
@cfy.pass_logger
@cfy.options.extended_view
def local_list(blueprint_id, logger):
    """Execute a workflow

    `WORKFLOW_ID` is the id of the workflow to execute (e.g. `uninstall`)
    """
    env = local.load_env(blueprint_id)
    executions = env.storage.get_executions()
    print_data(LOCAL_EXECUTION_COLUMNS, executions, 'Executions:',
               labels=EXECUTION_TABLE_LABELS)


@local_executions.command(
    name='get', short_help='Retrieve execution information')
@cfy.argument('execution-id')
@cfy.options.blueprint_id(required=True)
@cfy.options.common_options
@cfy.pass_logger
@cfy.options.extended_view
def local_get(execution_id, blueprint_id, logger):
    """Retrieve information for a specific execution

    `EXECUTION_ID` is the execution to get information on.
    """
    env = local.load_env(blueprint_id)
    execution = env.storage.get_execution(execution_id)
    if not execution:
        raise CloudifyCliError('Execution {0} not found'.format(execution_id))
    columns = LOCAL_EXECUTION_COLUMNS
    if get_global_json_output():
        columns += ['parameters']
    print_single(LOCAL_EXECUTION_COLUMNS, execution, 'Execution:',
                 labels=EXECUTION_TABLE_LABELS)
    if not get_global_json_output():
        print_details(execution['parameters'], 'Execution Parameters:')
