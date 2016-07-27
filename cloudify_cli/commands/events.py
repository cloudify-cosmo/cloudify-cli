########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

from cloudify_rest_client.exceptions import CloudifyClientError

from ..config import cfy
from ..logger import get_events_logger
from ..exceptions import CloudifyCliError, SuppressedCloudifyCliError
from ..execution_events_fetcher import ExecutionEventsFetcher, \
    wait_for_execution


@cfy.group(name='events')
@cfy.options.verbose
@cfy.assert_manager_active
def events():
    """Show events from workflow executions
    """
    pass


@events.command(name='list')
@cfy.argument('execution-id')
@cfy.options.include_logs
@cfy.options.json
@cfy.options.tail
@cfy.options.verbose
@cfy.add_logger
@cfy.add_client()
def list(execution_id, include_logs, json, tail, logger, client):
    """Display events for an execution

    `EXECUTION_ID` is the execution to list events for.
    """
    logger.info('Listing events for execution id {0} '
                '[include_logs={1}]'.format(execution_id, include_logs))
    try:
        execution_events = ExecutionEventsFetcher(
            client,
            execution_id,
            include_logs=include_logs)

        events_logger = get_events_logger(json)

        if tail:
            execution = wait_for_execution(client,
                                           client.executions.get(execution_id),
                                           events_handler=events_logger,
                                           include_logs=include_logs,
                                           timeout=None)   # don't timeout ever
            if execution.error:
                logger.info('Execution of workflow {0} for deployment '
                            '{1} failed. [error={2}]'.format(
                                execution.workflow_id,
                                execution.deployment_id,
                                execution.error))
                raise SuppressedCloudifyCliError()
            else:
                logger.info('Finished executing workflow {0} on deployment '
                            '{1}'.format(
                                execution.workflow_id,
                                execution.deployment_id))
        else:
            # don't tail, get only the events created until now and return
            events = execution_events.fetch_and_process_events(
                events_handler=events_logger)
            logger.info('\nTotal events: {0}'.format(events))
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Execution {0} not found'.format(execution_id))


@events.command(name='delete')
@cfy.argument('deployment-id')
@cfy.options.include_logs
@cfy.options.verbose
@cfy.add_logger
@cfy.add_client()
def delete(deployment_id, include_logs, logger, client):
    """Delete events attached to a deployment
    """
    logger.info(
        'Deleting events for deployment id {0} [include_logs={1}]'.format(
            deployment_id, include_logs))

    # Make sure the deployment exists - raise 404 otherwise
    client.deployments.get(deployment_id)
    deleted_events = client.events.delete(
        deployment_id, include_logs=include_logs)
    deleted_events = deleted_events.items[0]
    # TODO: There might be tens of thousands of events. We should probably
    # not print all of them.
    if deleted_events:
        logger.info('\nDeleted {0} events'.format(deleted_events))
    else:
        logger.info('\nNo events to delete')
