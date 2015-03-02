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


class ExecutionEventsFetcher(object):

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        self._timeout = value

    def __init__(self, client, execution_id, batch_size=100,
                 timeout=60, include_logs=False):
        self._client = client
        self._execution_id = execution_id
        self._batch_size = batch_size
        self._from_event = 0
        self._timeout = timeout
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

    def fetch_and_process_events(self, events_handler=None):
        total_events_count = 0
        deadline = time.time() + self._timeout

        while True:
            if time.time() > deadline:
                raise EventProcessingTimeoutError(
                    self._execution_id,
                    'events/log fetching timed out for execution timed out')

            events_batch_count = self._fetch_and_process_events_batch(
                events_handler=events_handler)

            total_events_count += events_batch_count

            if events_batch_count < self._batch_size:
                # returned less events than allowed by _batch_size,
                # this means these are the last events
                break

            time.sleep(1)

        return total_events_count


def get_all_execution_events(client, execution_id, include_logs=False):
    execution_events = ExecutionEventsFetcher(client,
                                              execution_id,
                                              include_logs=include_logs)
    return execution_events.fetch_all()


def get_deployment_environment_creation_execution(client, deployment_id):
    executions = client.executions.list(deployment_id=deployment_id)
    for e in executions:
        if e.workflow_id == 'create_deployment_environment':
            return e
    raise RuntimeError('Failed to get create_deployment_environment workflow '
                       'execution. Available executions: {0}'.format(
                           executions))


def wait_for_execution(client,
                       deployment_id,
                       execution,
                       events_handler=None,
                       include_logs=False,
                       timeout=900):

    # we must make sure the execution and event fetching loops can run at
    # least once (taking into account the 3-sec sleep here and possible
    # 1-sec sleep on event fetching)
    if timeout < 10:
        raise ValueError('execution timeout must be 10 seconds or longer')

    deadline = time.time() + timeout
    events_fetcher = ExecutionEventsFetcher(client, execution.id,
                                            include_logs=include_logs)
    # enforce a shorter timeout on event fetching if it's longer than the
    # execution timeout (taking into account the 3 sec sleep as well).
    # This is required because the user can set the execution timeout but not
    # the inner event fetcher timeout (defaults to 60 seconds)
    if events_fetcher.timeout-5 > timeout:
        events_fetcher.timeout = timeout-5

    # Poll for execution status until execution ends
    while execution.status not in Execution.END_STATES:
        if time.time() > deadline:
            raise ExecutionTimeoutError(
                execution.id,
                'execution of operation {0} for deployment {1} '
                'timed out'.format(execution.workflow_id, deployment_id))

        time.sleep(3)
        execution = client.executions.get(execution.id)
        if execution.status != Execution.PENDING:
            events_fetcher.fetch_and_process_events(
                events_handler=events_handler)

    return execution
