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

from .exceptions import (ExecutionTimeoutError,
                         EventProcessingTimeoutError)


WAIT_FOR_EXECUTION_SLEEP_INTERVAL = 3
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
                 execution_id,
                 batch_size=100,
                 include_logs=False):
        self._client = client
        self._execution_id = execution_id
        self._batch_size = batch_size
        self._from_event = 0
        self._include_logs = include_logs
        # make sure execution exists before proceeding
        # a 404 will be raised otherwise
        self._client.executions.get(execution_id)

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
            execution_id=self._execution_id,
            _offset=offset,
            _size=size,
            include_logs=self._include_logs,
            sort='reported_timestamp')
        self._from_event += len(events_list_response)
        return events_list_response

    def _map_api_event_to_internal_event(self, event):
        """Map data structure from API to internal.

        This method adapts the data structure returend by the events API
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
                    self._execution_id,
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


class EventsWatcher(object):
    """Wraps an event_handler function, examines events to check if an
    workflow execution finished has arrived.

    This will set its .end_log_received instance attribute to True,
    when it receives an event of type workflow_succeeded, workflow_cancelled
    or workflow_failed.

    :ivar end_log_received: was a "workflow execution finished" event seen?
    :vartype end_log_received: bool
    """

    def __init__(self, events_handler=None):
        self._events_handler = events_handler
        self.end_log_received = False

    def __call__(self, events):
        if self._events_handler is not None:
            self._events_handler(events)

        if any(self._is_end_event(evt) for evt in events):
            self.end_log_received = True

    def _is_end_event(self, event):
        """Is event a 'workflow execution finished' event?"""
        return event.get('event_type') in WORKFLOW_END_TYPES


def wait_for_execution(client,
                       execution,
                       events_handler=None,
                       include_logs=False,
                       timeout=900,
                       logger=None):

    # if execution already ended - return without waiting
    if execution.status in Execution.END_STATES:
        return execution

    if timeout is not None:
        deadline = time.time() + timeout

    events_fetcher = ExecutionEventsFetcher(client,
                                            execution.id,
                                            include_logs=include_logs)

    # Poll for execution status and execution logs, until execution ends
    # and we receive an event of type in WORKFLOW_END_TYPES
    execution_ended = False
    events_watcher = EventsWatcher(events_handler)

    # did we already see the execution status change, and are only waiting
    # for additional logs now?
    waiting_for_logs = False

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

        if not events_watcher.end_log_received and \
                execution.status != Execution.PENDING:
            events_fetcher.fetch_and_process_events(
                events_handler=events_watcher, timeout=timeout)

        if execution_ended and events_watcher.end_log_received:
            break

        # if the execution ended, wait one iteration for additional logs
        if execution_ended:
            if waiting_for_logs:
                if logger:
                    logger.info('Execution ended, but no end log message '
                                'received. Some logs might not have been '
                                'displayed.')
                break
            else:
                if logger:
                    logger.info('Execution ended, waiting {0} seconds for '
                                'additional log messages'
                                .format(WAIT_FOR_EXECUTION_SLEEP_INTERVAL))
                waiting_for_logs = True

        time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)

    return execution
