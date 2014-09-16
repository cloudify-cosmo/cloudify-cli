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
from cloudify_cli.exceptions import ExecutionTimeoutError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.executions import Execution


class ExecutionEventsFetcher(object):

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

    def fetch_and_process_events(self,
                                 get_remaining_events=False,
                                 events_handler=None):
        if events_handler is None:
            return
        events = self.fetch_events(get_remaining_events=get_remaining_events)
        events_handler(events)

    def fetch_events(self, get_remaining_events=False):
        if get_remaining_events:
            events = []
            timeout = time.time() + self._timeout
            while time.time() < timeout:
                result = self._fetch_events()
                if len(result) > 0:
                    events.extend(result)
                else:
                    return events
                time.sleep(1)
            raise RuntimeError('events/log fetching timed out')

        else:
            return self._fetch_events()

    def _fetch_events(self):
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

    def fetch_all(self):
        return self.fetch_events(get_remaining_events=True)


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

    deadline = time.time() + timeout
    execution_events = ExecutionEventsFetcher(client, execution.id,
                                              include_logs=include_logs)

    # Poll for execution status until execution ends
    while execution.status not in Execution.END_STATES:
        if time.time() > deadline:
            raise ExecutionTimeoutError(
                execution.id,
                'execution of operation {0} for deployment {1} '
                'timed out'.format(execution.workflow_id, deployment_id))

        time.sleep(3)

        execution = client.executions.get(execution.id)
        execution_events.fetch_and_process_events(
            events_handler=events_handler)

    # Process remaining events
    execution_events.fetch_and_process_events(
        get_remaining_events=True,
        events_handler=events_handler)

    return execution
