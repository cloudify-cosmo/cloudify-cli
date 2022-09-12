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


import time

from cloudify_rest_client.executions import Execution

from cloudify_cli.exceptions import (
    ExecutionTimeoutError,
    EventProcessingTimeoutError)


WAIT_FOR_EXECUTION_SLEEP_INTERVAL = 1
WORKFLOW_END_TYPES = {u'workflow_succeeded', u'workflow_failed',
                      u'workflow_cancelled'}


class ExecutionEventsFetcher(object):

    CONTEXT_FIELDS = [
        'deployment_id',
        'execution_id',
        'node_name',
        'operation',
        'workflow_id',
    ]

    def __init__(self,
                 client,
                 batch_size=100,
                 **list_kwargs):
        self._client = client
        self._list_kwargs = list_kwargs
        self._batch_size = batch_size
        self._from_event = 0
        # make sure execution/group exists before proceeding
        # a 404 will be raised otherwise
        if 'execution_id' in list_kwargs:
            self._client.executions.get(list_kwargs['execution_id'])
        elif 'execution_group_id' in list_kwargs:
            self._client.execution_groups.get(
                list_kwargs['execution_group_id'])

    def fetch_and_process_events_batch(self,
                                       events_handler=None,
                                       offset=None,
                                       size=None):
        events_list_response = self._fetch_events_batch(offset, size)
        total_events = events_list_response.metadata.pagination.total
        events = [
            self._map_api_event_to_internal_event(event)
            for event in events_list_response.items
        ]
        if events and events_handler:
            events_handler(events)

        return len(events), total_events

    def _fetch_events_batch(self, offset=None, size=None):
        offset = offset if offset is not None else self._from_event
        size = size if size is not None else self._batch_size
        events_list_response = self._client.events.list(
            _offset=offset,
            _size=size,
            sort='reported_timestamp',
            **self._list_kwargs
        )
        self._from_event += len(events_list_response)
        return events_list_response

    def _map_api_event_to_internal_event(self, event):
        """Map data structure from API to internal.

        This method adapts the data structure returned by the events API
        endpoint to the structure expected by `cloudify.event.Event`.

        Note: the event is modified in place, so even though the value is
        returned, the original data structure is not preserved.

        :param event: Event in API format
        :type event: dict(str)
        :return: Event in internal format
        :rtype: dict(str)

        """
        event['context'] = {
            context_field: event[context_field]
            for context_field in self.CONTEXT_FIELDS
        }
        for context_field in self.CONTEXT_FIELDS:
            del event[context_field]

        event['context']['node_id'] = event['node_instance_id']
        if 'source_id' in event:
            event['context']['source_id'] = event['source_id']
            event['context']['target_id'] = event['target_id']
        del event['node_instance_id']

        event['message'] = {
            'arguments': None,
            'text': event['message'],
        }

        event['context']['task_error_causes'] = event['error_causes']
        del event['error_causes']

        return event

    def fetch_and_process_events(self, events_handler=None, timeout=60):
        total_events_count = 0
        # timeout can be None (never time out), for example when tail is used
        if timeout is not None:
            deadline = time.time() + timeout

        while True:
            if timeout is not None and time.time() > deadline:
                raise EventProcessingTimeoutError(
                    self._list_kwargs.get('execution_id') or
                    self._list_kwargs.get('execution_group_id'),
                    'events/log fetching timed out')

            events_batch_count, _ = self.fetch_and_process_events_batch(
                events_handler=events_handler)

            total_events_count += events_batch_count
            if events_batch_count < self._batch_size:
                # returned less events than allowed by _batch_size,
                # this means these are the last events found so far
                break

        return total_events_count


def get_deployment_environment_creation_execution(client, deployment_id):
    executions = client.executions.list(deployment_id=deployment_id)
    for e in executions:
        if e.workflow_id == 'create_deployment_environment':
            return e
    raise RuntimeError(
        'Failed to get create_deployment_environment workflow '
        'execution. Available executions: {0}'.format(executions))


def wait_for_execution(client,
                       execution,
                       events_handler=None,
                       include_logs=False,
                       timeout=900,
                       logger=None,
                       from_datetime=None):

    # if execution already ended - return without waiting
    if execution.status in Execution.END_STATES:
        return execution

    if timeout is not None:
        deadline = time.time() + timeout

    events_fetcher = ExecutionEventsFetcher(client,
                                            execution_id=execution.id,
                                            include_logs=include_logs,
                                            from_datetime=from_datetime)

    # Poll for execution status and execution logs, until execution ends
    execution_ended = False

    while True:
        if timeout is not None:
            if time.time() > deadline:
                raise ExecutionTimeoutError(
                    execution.id,
                    'execution of operation {0} for deployment {1} '
                    'timed out'.format(execution.workflow_id,
                                       execution.deployment_id))
            else:
                # update the remaining timeout
                timeout = deadline - time.time()

        if not execution_ended:
            execution = client.executions.get(execution.id)
            execution_ended = execution.status in Execution.END_STATES

        events_fetcher.fetch_and_process_events(
            events_handler=events_handler, timeout=timeout)

        if execution_ended:
            break

        time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)

    return execution


def wait_for_execution_group(client,
                             execution_group,
                             events_handler=None,
                             include_logs=False,
                             timeout=900,
                             logger=None,
                             from_datetime=None):
    """Like wait_for_execution, but for a group"""
    if execution_group.status in Execution.END_STATES:
        return execution_group

    if logger is not None and execution_group.status == Execution.QUEUED:
        logger.info("Executions have been queued: you can keep waiting "
                    "for the executions to start or interrupt (eg. ^C).\n")

    if timeout is not None:
        deadline = time.time() + timeout

    events_fetcher = ExecutionEventsFetcher(
        client,
        execution_group_id=execution_group.id,
        include_logs=include_logs,
        from_datetime=from_datetime)

    # Poll for execution status and execution logs, until execution ends
    group_finished = False

    while True:
        if timeout is not None:
            if time.time() > deadline:
                raise ExecutionTimeoutError(
                    execution_group.id,
                    'execution of operation {0} for deployment group {1} '
                    'timed out'.format(execution_group.workflow_id,
                                       execution_group.deployment_group_id))
            else:
                # update the remaining timeout
                timeout = deadline - time.time()

        if not group_finished:
            execution_group = client.execution_groups.get(execution_group.id)
            group_finished = execution_group.status in Execution.END_STATES

        events_fetcher.fetch_and_process_events(
            events_handler=events_handler, timeout=timeout)

        if group_finished:
            break

        time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)

    return execution_group
