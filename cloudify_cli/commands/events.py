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

from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify import logs

import click

from cloudify_cli import utils
from cloudify_cli.cli import cfy
from cloudify_cli.logger import get_events_logger
from cloudify_cli.exceptions import (
    CloudifyCliError,
    SuppressedCloudifyCliError)
from cloudify_cli.execution_events_fetcher import (
    ExecutionEventsFetcher,
    wait_for_execution,
    wait_for_execution_group)


@cfy.group(name='events')
@cfy.options.common_options
@cfy.assert_manager_active()
def events():
    """Show events from workflow executions
    """
    pass


@events.command(
    name='list',
    short_help='List deployments events [manager only]',
)
@cfy.argument('execution-id', required=False)
@cfy.options.execution_id(required=False, dest='execution_id_opt')
@click.option(
    '--execution-group', '-g',
    help='The execution group ID to list the events for',
    cls=cfy.MutuallyExclusiveOption,
    mutually_exclusive=['execution_id_opt'],
)
@cfy.options.worker_names
@cfy.options.include_logs
@cfy.options.json_output
@cfy.options.tail
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='execution')
@cfy.options.from_datetime(
    required=False,
    help="List events that occurred at this timestamp or after"
)
@cfy.options.to_datetime(
    required=False,
    mutually_exclusive_with=['tail', 'before'],
    help="List events that occurred at this timestamp or before",
)
@cfy.options.before(
    required=False,
    mutually_exclusive_with=['tail', 'to_datetime'],
    help="List events that occurred this long ago or earlier",
)
@click.option('--node', help='List events for this node')
@click.option(
    '--operation',
    help='List events for this interface operation '
         '(eg. cloudify.interfaces.lifecycle.create)',
)
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.pass_client()
@cfy.pass_logger
def list(execution_id,
         execution_id_opt,
         execution_group,
         include_logs,
         json_output,
         tail,
         tenant_name,
         from_datetime,
         to_datetime,
         before,
         pagination_offset,
         pagination_size,
         with_worker_names,
         node,
         operation,
         client,
         logger):
    """Display events for an execution"""
    if execution_id and execution_id_opt:
        raise click.UsageError(
            "Execution ID provided both as a positional "
            "argument ('{}') and as an option ('{}'). "
            "Please only specify it once (preferably as "
            "a positional argument).".format(
                execution_id,
                execution_id_opt))

    if not execution_id:
        execution_id = execution_id_opt
        if execution_id:
            logger.warning("Providing the execution ID as an option (using "
                           "'-e') is now deprecated. Please provide the "
                           "execution ID as a positional argument.")

    if not (execution_id or execution_group):
        raise click.UsageError('Provide one of the following: Execution ID or '
                               'Execution Group ID')

    if execution_id and execution_group:
        raise click.UsageError('Provide either Execution ID or Execution '
                               'Group ID, not both')

    if before:
        to_datetime = before

    if execution_id:
        logger.info(
            'Listing events for execution id %s [%s]',
            execution_id,
            _filter_description(include_logs, from_datetime, to_datetime),
        )
        execution_selection = {
            'execution_id': execution_id
        }
        wait_for_method = wait_for_execution
        wait_for_record = client.executions.get(execution_id)
    else:
        logger.info(
            'Listing events for execution group %s [%s]',
            execution_group,
            _filter_description(include_logs, from_datetime, to_datetime),
        )
        execution_selection = {
            'execution_group_id': execution_group
        }
        wait_for_method = wait_for_execution_group
        wait_for_record = client.execution_groups.get(execution_group)

    utils.explicit_tenant_name_message(tenant_name, logger)
    try:
        execution_events = ExecutionEventsFetcher(
            client,
            include_logs=include_logs,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            node_id=node,
            operation=operation,
            **execution_selection
        )

        events_logger = get_events_logger(json_output, with_worker_names)

        if tail:
            execution = wait_for_method(
                client,
                wait_for_record,
                events_handler=events_logger,
                include_logs=include_logs,
                timeout=None,  # don't timeout ever
                from_datetime=from_datetime,
            )
            if hasattr(execution, 'error') and execution.error:
                logger.info(
                    'Execution of workflow %s for deployment %s failed. '
                    '[error=%s]',
                    execution.workflow_id,
                    execution.deployment_id,
                    execution.error,
                )
                raise SuppressedCloudifyCliError()
            if hasattr(execution, 'workflow_id'):
                if hasattr(execution, 'deployment_id'):
                    logger.info(
                        'Finished executing workflow %s on deployment %s',
                        execution.workflow_id,
                        execution.deployment_id,
                    )
                elif hasattr(execution, 'deployment_group_id'):
                    logger.info(
                        'Finished executing workflow %s '
                        'on deployment group %s',
                        execution.workflow_id,
                        execution.deployment_group_id,
                    )
            else:
                logger.info('Finished executing %s', wait_for_record.id)

        else:
            # don't tail, get only the events created until now and return
            current_events, total_events = execution_events. \
                fetch_and_process_events_batch(events_handler=events_logger,
                                               offset=pagination_offset,
                                               size=pagination_size)
            logger.info(
                '\nShowing %s of %s events', current_events, total_events)
            if not json_output:
                logger.info('Debug messages are only shown when you use very '
                            'verbose mode (-vv)')
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Execution {0} not found'.format(execution_id))


@events.command(name='delete',
                short_help='Delete deployment events [manager only]')
@cfy.argument('deployment-id')
@cfy.options.include_logs
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.from_datetime(required=False,
                           help="Events that occurred at this timestamp"
                                " or after will be deleted")
@cfy.options.to_datetime(required=False,
                         mutually_exclusive_with=['before'],
                         help="Events that occurred at this timestamp"
                              " or before will be deleted")
@cfy.options.before(required=False,
                    mutually_exclusive_with=['to_datetime'],
                    help="Events that occurred this long ago or earlier "
                         "will be deleted (e.g. '2 weeks')")
@cfy.options.store_before()
@cfy.options.store_output_path()
@cfy.pass_client()
@cfy.pass_logger
def delete(deployment_id, include_logs, logger, client, tenant_name,
           from_datetime, to_datetime, before, store_before, output_path):
    """Delete events attached to a deployment

    `DEPLOYMENT_ID` is the deployment_id of the executions from which
    events/logs are deleted.
    """
    if before:
        to_datetime = before

    utils.explicit_tenant_name_message(tenant_name, logger)
    filter_description = _filter_description(include_logs, from_datetime,
                                             to_datetime)
    logger.info('Deleting events for deployment id {0} [{1}]'.format(
        deployment_id, filter_description))

    # Make sure the deployment exists - raise 404 otherwise
    client.deployments.get(deployment_id)

    # List events prior to their deletion
    if store_before and output_path:
        exec_list = client.executions.list(deployment_id=deployment_id,
                                           include_system_workflows=True,
                                           _all_tenants=True)
        with open(output_path, 'w') as output_file:
            click.echo(
                'Events for deployment id {0} [{1}]'.format(
                    deployment_id, filter_description),
                file=output_file,
                nl=True)
            events_logger = DeletedEventsLogger(output_file)
            for execution in exec_list:
                execution_events = ExecutionEventsFetcher(
                    client,
                    execution_id=execution.id,
                    include_logs=include_logs,
                    from_datetime=from_datetime,
                    to_datetime=to_datetime)
                output_file = open(output_path, 'a') if output_path else None
                click.echo(
                    '\nListing events for execution id {0}\n'.format(
                        execution.id),
                    file=output_file,
                    nl=True)
                total_events = execution_events.fetch_and_process_events(
                    events_handler=events_logger.log)
                click.echo(
                    '\nListed {0} events'.format(total_events),
                    file=output_file,
                    nl=True)

    # Delete events
    delete_args = {}
    if store_before and not output_path:
        delete_args['store_before'] = 'true'
    deleted_events_count = client.events.delete(
        deployment_id, include_logs=include_logs,
        from_datetime=from_datetime, to_datetime=to_datetime,
        **delete_args)
    deleted_events_count = deleted_events_count.items[0]
    if deleted_events_count:
        logger.info('\nDeleted {0} events'.format(deleted_events_count))
    else:
        logger.info('\nNo events to delete')


def _filter_description(include_logs, from_datetime, to_datetime):
    filter_info = {'include_logs': u'{0}'.format(include_logs)}
    if from_datetime:
        filter_info['from_datetime'] = u'{0}'.format(from_datetime)
    if to_datetime:
        filter_info['to_datetime'] = u'{0}'.format(to_datetime)
    return u', '.join(u'{0}={1}'.format(k, v) for k, v in
                      filter_info.items())


class DeletedEventsLogger(object):
    def __init__(self, output_file=None):
        self._output_file = output_file

    def log(self, events):
        """The default events logger prints events as short messages.

        :param events: The events to print.
        :return:
        """
        for event in events:
            output = logs.create_event_message_prefix(event)
            if output:
                click.echo(output, file=self._output_file)
