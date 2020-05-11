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
import re
import datetime

from .. import utils
from ..cli import cfy
from ..logger import get_events_logger
from ..exceptions import CloudifyCliError, SuppressedCloudifyCliError
from ..execution_events_fetcher import ExecutionEventsFetcher, \
    wait_for_execution


@cfy.group(name='events')
@cfy.options.common_options
@cfy.assert_manager_active()
def events():
    """Show events from workflow executions
    """
    pass


@events.command(name='list',
                short_help='List deployments events [manager only]')
@cfy.argument('execution-id', required=False)
@cfy.options.execution_id(required=False, dest='execution_id_opt')
@cfy.options.include_logs
@cfy.options.json_output
@cfy.options.tail
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='execution')
@cfy.options.from_datetime(required=False,
                           help="Events that occurred at this timestamp"
                                " or after will be listed")
@cfy.options.to_datetime(required=False,
                         mutually_exclusive_with=['tail'],
                         help="Events that occurred at this timestamp"
                              " or before will be listed",)
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.pass_client()
@cfy.pass_logger
def list(execution_id,
         execution_id_opt,
         include_logs,
         json_output,
         tail,
         tenant_name,
         from_datetime,
         to_datetime,
         pagination_offset,
         pagination_size,
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
        if not execution_id:
            raise click.UsageError('Execution ID not provided')
        logger.warning("Providing the execution ID as an option (using '-e') "
                       "is now deprecated. Please provide the execution ID as "
                       "a positional argument.")

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing events for execution id {0} '
                '[include_logs={1}]'.format(execution_id, include_logs))
    try:
        execution_events = ExecutionEventsFetcher(
            client,
            execution_id,
            include_logs=include_logs,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

        events_logger = get_events_logger(json_output)

        if tail:
            execution = wait_for_execution(client,
                                           client.executions.get(execution_id),
                                           events_handler=events_logger,
                                           include_logs=include_logs,
                                           timeout=None,  # don't timeout ever
                                           from_datetime=from_datetime)
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
            current_events, total_events = execution_events. \
                fetch_and_process_events_batch(events_handler=events_logger,
                                               offset=pagination_offset,
                                               size=pagination_size)
            logger.info('\nShowing {0} of {1} events'.format(current_events,
                                                             total_events))
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
                    help="Events that occurred this long ago or earlier"
                         "will be deleted")
@cfy.options.list_before_deletion()
@cfy.options.list_output_path()
@cfy.pass_client()
@cfy.pass_logger
def delete(deployment_id, include_logs, logger, client, tenant_name,
           from_datetime, to_datetime, before,
           list_before_deletion, output_path):
    """Delete events attached to a deployment

    `DEPLOYMENT_ID` is the deployment_id of the executions from which
    events/logs are deleted.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    if before:
        to_datetime = _parse_before(before)
    filter_info = {'include_logs': u'{0}'.format(include_logs)}
    if from_datetime:
        filter_info['from_datetime'] = u'{0}'.format(from_datetime)
    if to_datetime:
        filter_info['to_datetime'] = u'{0}'.format(to_datetime)
    logger.info(
        'Deleting events for deployment id {0} [{1}]'.format(
            deployment_id,
            u', '.join([u'{0}={1}'.format(k, v) for k, v in
                        filter_info.items()])))

    # Make sure the deployment exists - raise 404 otherwise
    client.deployments.get(deployment_id)

    # List events prior to their deletion
    if list_before_deletion:
        exec_list = client.executions.list(deployment_id=deployment_id,
                                           include_system_workflows=True,
                                           _all_tenants=True)
        if len(exec_list) > 0 and output_path:
            with open(output_path, 'w') as output_file:
                click.echo(
                    'Events for deployment id {0} [{1}]\n'.format(
                        deployment_id,
                        u', '.join([u'{0}={1}'.format(k, v) for k, v in
                                    filter_info.items()])),
                    file=output_file,
                    nl=True)
        for execution in exec_list:
            execution_events = ExecutionEventsFetcher(
                client, execution.id, include_logs=include_logs,
                from_datetime=from_datetime, to_datetime=to_datetime)
            output_file = open(output_path, 'a') if output_path else None
            click.echo(
                'Listing events for execution id {0}\n'.format(execution.id),
                file=output_file,
                nl=True)
            events_logger = DeletedEventsLogger(output_file)
            total_events = execution_events.fetch_and_process_events(
                events_handler=events_logger.log)
            click.echo(
                '\nListed {0} events'.format(total_events),
                file=output_file,
                nl=True)
            if output_file:
                output_file.close()

    # Delete events
    delete_args = {}
    if list_before_deletion and not output_path:
        delete_args['store_before_deletion'] = 'True'
    deleted_events_count = client.events.delete(
        deployment_id, include_logs=include_logs,
        from_datetime=from_datetime, to_datetime=to_datetime,
        **delete_args)
    deleted_events_count = deleted_events_count.items[0]
    if deleted_events_count:
        logger.info('\nDeleted {0} events'.format(deleted_events_count))
    else:
        logger.info('\nNo events to delete')


def _parse_before(ago):
    """Change relative time (ago) to a valid timestamp"""
    parsed = re.findall(r"(\d+) (seconds?|minutes?|hours?|days?|weeks?"
                        "|months?|years?) ?(ago)?",
                        ago)
    if parsed and len(parsed[0]) > 1:
        number = int(parsed[0][0])
        period = parsed[0][1]
        if period[-1] != u's':
            period += u's'
        now = datetime.datetime.utcnow()
        if period == u'years':
            result = now.replace(year=now.year - number)
        elif period == u'months':
            if now.month > number:
                result = now.replace(month=now.month - number)
            else:
                result = now.replace(month=now.month - number + 12,
                                     year=now.year - 1)
        else:
            delta = datetime.timedelta(**{period: number})
            result = now - delta
        return result.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


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
