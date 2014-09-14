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


import datetime

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.blueprints import BlueprintsClient, Blueprint
from cloudify_rest_client.client import HTTPClient
from cloudify_rest_client.deployments import DeploymentsClient, Deployment
from cloudify_rest_client.events import EventsClient
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.executions import ExecutionsClient, Execution
from cloudify_rest_client.manager import ManagerClient
from cloudify_rest_client.node_instances import NodeInstancesClient
from cloudify_rest_client.nodes import NodesClient
from cloudify_rest_client.search import SearchClient


class MockExecutionsClient(ExecutionsClient):

    # def get(self, execution_id, _include=None):
    #     execution = {
    #         'status': 'terminated',
    #         'workflow_id': 'mock_wf',
    #         'deployment_id': 'deployment-id',
    #         'blueprint_id': 'blueprint-id',
    #         'error': '',
    #         'id': id,
    #         'created_at': datetime.datetime.now(),
    #         'parameters': {}}
    #     return Execution(execution)

    def get(self, execution_id, _include=None):
        pass


class MockEventsClient(EventsClient):

    # events = []
    #
    # def get(self, execution_id, from_event=0,
    #         batch_size=100, include_logs=False):
    #     if from_event >= len(self.events):
    #         return [], len(self.events)
    #     until_event = min(from_event + batch_size, len(self.events))
    #     return self.events[from_event:until_event], len(self.events)

    def get(self, execution_id, from_event=0,
            batch_size=100, include_logs=False):
        pass


class MockBlueprintsClient(BlueprintsClient):

    # def delete(self, blueprint_id):
    #     pass
    #
    # def upload(self, blueprint_path, blueprint_id):
    #     return Blueprint({'id': blueprint_id})
    #
    # def download(self, blueprint_id, output_file=None):
    #     pass
    #
    # def get(self, blueprint_id, _include=None):
    #     return Blueprint({'id': blueprint_id})
    #
    # def list(self, _include=None):
    #     return []

    def delete(self, blueprint_id):
        pass

    def upload(self, blueprint_path, blueprint_id):
        pass

    def download(self, blueprint_id, output_file=None):
        pass

    def get(self, blueprint_id, _include=None):
        pass

    def list(self, _include=None):
        pass


class MockDeploymentClient(DeploymentsClient):

    # def delete(self, deployment_id, ignore_live_nodes=False):
    #     pass
    #
    # def list_executions(self, deployment_id):
    #     return []
    #
    # def list(self, _include=None):
    #     return []
    #
    # def get(self, deployment_id, _include=None):
    #     if id == 'nonexistent-dep':
    #         raise CloudifyClientError("deployment {0} doesn't exist"
    #                                   .format('nonexistent-dep'),
    #                                   status_code=404)
    #     deployment = {
    #         'blueprint_id': 'mock_blueprint_id',
    #         'workflows': [{
    #             'created_at': None,
    #             'name': 'mock_workflow',
    #             'parameters': {
    #                 'test-key': {
    #                     'default': 'test-value'
    #                 },
    #                 'test-mandatory-key': {},
    #                 'test-nested-key': {
    #                     'default': {
    #                         'key': 'val'
    #                     }
    #                 }
    #             }
    #         }]
    #     }
    #     return Deployment(deployment)
    #
    # def create(self, blueprint_id, deployment_id, inputs=None):
    #     return Deployment({
    #         'deployment_id': deployment_id
    #     })
    #
    # def execute(self, deployment_id, workflow_id,
    #             parameters=None,
    #             allow_custom_parameters=False,
    #             force=False):
    #     if workflow_id != 'install':
    #         raise CloudifyClientError("operation {0} doesn't exist"
    #                                   .format(workflow_id), 400)
    #     return Execution({'status': 'terminated'})

    def delete(self, deployment_id, ignore_live_nodes=False):
        pass

    def list_executions(self, deployment_id):
        pass

    def list(self, _include=None):
        pass

    def get(self, deployment_id, _include=None):
        pass

    def create(self, blueprint_id, deployment_id, inputs=None):
        pass

    def execute(self, deployment_id, workflow_id,
                parameters=None,
                allow_custom_parameters=False,
                force=False):
        pass


class MockNodesClient(NodesClient):
    pass


class MockNodeInstancesClient(NodeInstancesClient):
    pass


class MockManagerClient(ManagerClient):

    # provider_context = {}
    # provider_name = None
    #
    # def get_status(self):
    #     return {
    #         'status': 'running',
    #         'services': []
    #     }
    #
    # def get_context(self, _include=None):
    #     return {
    #         'name': self.provider_name,
    #         'context': self.provider_context
    #     }
    #
    # def create_context(self, provider_name, provider_context):
    #     self.provider_name = provider_name
    #     self.provider_context = provider_context

    def get_status(self):
        pass

    def get_context(self, _include=None):
        pass

    def create_context(self, provider_name, provider_context):
        pass


class MockSearchClient(SearchClient):
    pass


class MockApi(HTTPClient):
    pass


class MockCloudifyClient(CloudifyClient):

    def __init__(self, management_ip='localhost'):
        mock_api = MockApi(host=management_ip)
        self.blueprints = MockBlueprintsClient(api=mock_api)
        self.deployments = MockDeploymentClient(api=mock_api)
        self.executions = MockExecutionsClient(api=mock_api)
        self.nodes = MockNodesClient(api=mock_api)
        self.node_instances = MockNodeInstancesClient(api=mock_api)
        self.manager = MockManagerClient(api=mock_api)
        self.events = MockEventsClient(api=mock_api)
        self.search = MockSearchClient(api=mock_api)
