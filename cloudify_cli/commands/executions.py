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

import json
import time

from cloudify_rest_client import exceptions

from .. import local
from .. import utils
from ..table import print_data
from ..cli import cfy, helptexts
from ..logger import get_events_logger
from ..constants import DEFAULT_UNINSTALL_WORKFLOW
from ..execution_events_fetcher import wait_for_execution
from ..exceptions import CloudifyCliError, ExecutionTimeoutError, \
    SuppressedCloudifyCliError

_STATUS_CANCELING_MESSAGE = (
    'NOTE: Executions currently in a "canceling/force-canceling" status '
    'may take a while to change into "cancelled"')

EXECUTION_COLUMNS = ['id', 'workflow_id', 'status', 'deployment_id',
                     'created_at', 'error', 'visibility', 'tenant_name',
                     'created_by']


@cfy.group(name='executions')
@cfy.options.verbose()
def executions():
    """Handle workflow executions
    """
    pass


@cfy.command(name='get',
             short_help='Retrieve execution information [manager only]')
@cfy.argument('execution-id')
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='execution')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_get(execution_id, logger, client, tenant_name):
    """Retrieve information for a specific execution

    `EXECUTION_ID` is the execution to get information on.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    try:
        logger.info('Retrieving execution {0}'.format(execution_id))
        execution = client.executions.get(execution_id)
    except exceptions.CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Execution {0} not found'.format(execution_id))

    print_data(EXECUTION_COLUMNS, execution, 'Execution:', max_width=50)

    # print execution parameters
    logger.info('Execution Parameters:')
    for param_name, param_value in utils.decode_dict(
            execution.parameters).iteritems():
        logger.info('\t{0}: \t{1}'.format(param_name, param_value))
    if execution.status in (execution.CANCELLING, execution.FORCE_CANCELLING):
        logger.info(_STATUS_CANCELING_MESSAGE)
    logger.info('')


@cfy.command(name='list',
             short_help='List deployment executions [manager only]')
@cfy.options.deployment_id(required=False)
@cfy.options.include_system_workflows
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='execution')
@cfy.options.all_tenants
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
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
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
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
            _size=pagination_size
        )

    except exceptions.CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} does not exist'.format(
            deployment_id))

    print_data(EXECUTION_COLUMNS, executions, 'Executions:')
    total = executions.metadata.pagination.total
    logger.info('Showing {0} of {1} executions'.format(len(executions), total))

    if any(execution.status in (
            execution.CANCELLING, execution.FORCE_CANCELLING)
            for execution in executions):
        logger.info(_STATUS_CANCELING_MESSAGE)


@cfy.command(name='start',
             short_help='Execute a workflow [manager only]')
@cfy.argument('workflow-id')
@cfy.options.deployment_id(required=True)
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.force(help=helptexts.FORCE_CONCURRENT_EXECUTION)
@cfy.options.timeout()
@cfy.options.include_logs
@cfy.options.json_output
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='execution')
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
                  logger,
                  client,
                  tenant_name):
    """Execute a workflow on a given deployment

    `WORKFLOW_ID` is the id of the workflow to execute (e.g. `uninstall`)
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    events_logger = get_events_logger(json_output)
    events_message = "* Run 'cfy events list -e {0}' to retrieve the " \
                     "execution's events/logs"
    original_timeout = timeout
    logger.info('Executing workflow {0} on deployment {1} '
                '[timeout={2} seconds]'.format(
                    workflow_id,
                    deployment_id,
                    timeout))
    try:
        try:
            execution = client.executions.start(
                deployment_id,
                workflow_id,
                parameters=parameters,
                allow_custom_parameters=allow_custom_parameters,
                force=force)
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
                               _get_deployment_environment_creation_execution(
                                   client, deployment_id),
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
                force=force)

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
                              "--execution-id {0}' to retrieve the " \
                              "execution's events/logs"
        logger.info(events_tail_message.format(e.execution_id))
        raise SuppressedCloudifyCliError()


@cfy.command(name='cancel',
             short_help='Cancel a workflow execution [manager only]')
@cfy.argument('execution-id')
@cfy.options.force(help=helptexts.FORCE_CANCEL_EXECUTION)
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='execution')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_cancel(execution_id, force, logger, client, tenant_name):
    """Cancel a workflow's execution

    `EXECUTION_ID` is the ID of the execution to cancel.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('{0}Cancelling execution {1}'.format(
        'Force-' if force else '', execution_id))
    client.executions.cancel(execution_id, force)
    logger.info(
        "A cancel request for execution {0} has been sent. "
        "To track the execution's status, use:\n"
        "cfy executions get {0}".format(execution_id))


def _get_deployment_environment_creation_execution(client, deployment_id):
    executions = client.executions.list(deployment_id=deployment_id)
    for execution in executions:
        if execution.workflow_id == 'create_deployment_environment':
            return execution
    raise RuntimeError('Failed to get create_deployment_environment '
                       'workflow execution.'
                       'Available executions: {0}'.format(executions))


@cfy.command(name='start',
             short_help='Execute a workflow')
@cfy.argument('workflow-id')
@cfy.options.blueprint_id(required=True, multiple_blueprints=True)
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.task_retries()
@cfy.options.task_retry_interval()
@cfy.options.task_thread_pool_size()
@cfy.options.verbose()
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
