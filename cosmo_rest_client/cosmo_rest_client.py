__author__ = 'ran'

import tempfile
import os
import time
import shutil
import tarfile
import json

from contextlib import contextmanager
from urllib2 import HTTPError, URLError

from swagger.swagger import ApiClient
from swagger.BlueprintsApi import BlueprintsApi
from swagger.ExecutionsApi import ExecutionsApi
from swagger.DeploymentsApi import DeploymentsApi


class CosmoRestClient(object):

    def __init__(self, server_url):
        api_client = ApiClient(apiServer=server_url, apiKey='')
        self.blueprints_api = BlueprintsApi(api_client)
        self.executions_api = ExecutionsApi(api_client)
        self.deployments_api = DeploymentsApi(api_client)

    def publish_blueprint(self, blueprint_path):
        tempdir = tempfile.mkdtemp()
        try:
            tar_path = self._tar_blueprint(blueprint_path, tempdir)
            application_file = os.path.basename(blueprint_path)

            with self._protected_call_to_server('publishing blueprint'):
                with open(tar_path, 'rb') as f:
                    blueprint_state = self.blueprints_api.upload(f.read(), application_file_name=application_file)

                return blueprint_state
        finally:
            shutil.rmtree(tempdir)

    def create_deployment(self, blueprint_id):
        with self._protected_call_to_server('creating new deployment'):
            body = {
                'blueprintId': blueprint_id
            }
            return self.deployments_api.createDeployment(body=body)

    def execute_deployment(self, deployment_id, operation, events_handler, timeout=900):
        end = time.time() + timeout

        with self._protected_call_to_server('executing deployment operation'):
            body = {
                'workflowId': operation
            }
            execution = self.deployments_api.execute(deployment_id=deployment_id, body=body)

            deployment_prev_events_size = 0
            next_event_index = 0
            has_more_events = False
            end_states = ('terminated', 'failed')

            def is_handle_events():
                return events_handler and \
                       (has_more_events or self._check_for_deployment_events(deployment_id, deployment_prev_events_size))

            while execution.status not in end_states:
                if end < time.time():
                    raise RuntimeError('Timeout executing deployment operation {0} of deployment {1}'.format(
                                       operation, deployment_id))
                time.sleep(1)

                if is_handle_events():
                    (next_event_index, has_more_events, deployment_prev_events_size) = \
                        self._get_and_handle_deployment_events(deployment_id, events_handler, next_event_index)

                execution = self.executions_api.getById(execution.id)

            if is_handle_events():
                self._handle_remaining_deployment_events(deployment_id, events_handler, next_event_index)

            if execution.status != 'terminated':
                raise RuntimeError('Execution of deployment operation {0} of deployment {1} failed. (status response:'
                                   ' {2})'.format(operation, deployment_id, execution.error))

    def _check_for_deployment_events(self, deployment_id, deployment_prev_events_size):
        response_headers_buffer = {}
        self.deployments_api.eventsHeaders(deployment_id, response_headers_buffer)
        return response_headers_buffer['deployment-events-bytes'] > deployment_prev_events_size

    def _get_and_handle_deployment_events(self, deployment_id, events_handler, from_param=0, count_param=500):
        response_headers_buffer = {}
        deployment_events = self.deployments_api.readEvents(deployment_id, response_headers_buffer,
                                                            from_param=from_param, count_param=count_param)
        events_handler(deployment_events.events)
        return (deployment_events.lastEvent + 1,
                from_param + count_param < deployment_events.deploymentTotalEvents,
                response_headers_buffer['deployment-events-bytes'])

    def _handle_remaining_deployment_events(self, deployment_id, events_handler, next_event_index=0):
        has_more_events = True
        while has_more_events:
            (next_event_index, has_more_events, _) = \
                self._get_and_handle_deployment_events(deployment_id, events_handler, next_event_index)

    @staticmethod
    def _tar_blueprint(blueprint_path, tempdir):
        blueprint_name = os.path.basename(os.path.splitext(blueprint_path)[0])
        blueprint_directory = os.path.dirname(blueprint_path)
        tar_path = '{0}/{1}.tar.gz'.format(tempdir, blueprint_name)
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(blueprint_directory, arcname=os.path.basename(blueprint_directory))
        return tar_path

    @staticmethod
    @contextmanager
    def _protected_call_to_server(action_name):
        try:
            yield
        except HTTPError, ex:
            server_message = None
            if ex.fp:
                server_output = json.loads(ex.fp.read())
                if 'message' in server_output:
                    server_message = server_output['message']
            raise RuntimeError('Failed {0}: Error code - {1}; Message - "{2}"'
                               .format(action_name, ex.code, server_message if server_message else ex.msg))
        except URLError, ex:
            raise RuntimeError('Failed {0}: Reason - {1}'.format(action_name, ex.reason))