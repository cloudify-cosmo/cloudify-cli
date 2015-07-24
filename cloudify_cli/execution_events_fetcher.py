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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
import time
from cloudify_cli.exceptions import ExecutionTimeoutError, \
    EventProcessingTimeoutError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.executions import Execution


WAIT_FOR_EXECUTION_SLEEP_INTERVAL = 3


class ExecutionEventsFetcher(object):

    def __init__(self, client, execution_id, batch_size=100,
                 include_logs=False):
        self._client = client
        self._execution_id = execution_id
        self._batch_size = batch_size
        self._from_event = 0
        self._include_logs = include_logs
        # make sure execution exists before proceeding
        # a 404 will be raised otherwise
        self._client.executions.get(execution_id)

    def _fetch_and_process_events_batch(self, events_handler=None):
        events = self._fetch_events_batch()
        if events and events_handler:
            events_handler(events)

        return len(events)

    def _fetch_events_batch(self):
        try:
            events, total = self._client.events.get(
                self._execution_id,
                from_event=self._from_event,
                batch_size=self._batch_size,
                include_logs=self._include_logs)
            self._from_event += len(events)
        except CloudifyClientError, e:
            # A workaround in a case where events index was not yet created.
            # This can happen if there were no events sent to logstash.
            if e.status_code == 500 and 'IndexMissingException' in e.message:
                return []
            raise
        return events

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

            events_batch_count = self._fetch_and_process_events_batch(
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
    raise RuntimeError('Failed to get create_deployment_environment workflow '
                       'execution. Available executions: {0}'.format(
                           executions))


def wait_for_execution(client,
                       execution,
                       events_handler=None,
                       include_logs=False,
                       timeout=900):

    # if execution already ended - return without waiting
    if execution.status in Execution.END_STATES:
        return execution

    if timeout is not None:
        deadline = time.time() + timeout

    events_fetcher = ExecutionEventsFetcher(client, execution.id,
                                            include_logs=include_logs)

    # Poll for execution status until execution ends
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
                timeout = deadline-time.time()

        if execution.status != Execution.PENDING:
            events_fetcher.fetch_and_process_events(
                events_handler=events_handler, timeout=timeout)

        execution = client.executions.get(execution.id)
        if execution.status in Execution.END_STATES:
            # fetching any last events the execution might have
            events_fetcher.fetch_and_process_events(
                events_handler=events_handler, timeout=timeout)
            break
        time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)

    return execution
