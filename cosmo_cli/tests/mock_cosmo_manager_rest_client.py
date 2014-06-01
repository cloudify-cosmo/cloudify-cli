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

__author__ = 'ran'

from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import CosmoManagerRestCallError

_provider_context = {}
_provider_name = 'mock_provider'


def get_mock_provider_name():
    return _provider_name


class MockCosmoManagerRestClient(object):

    """
    A mock of the rest client, containing only the methods and object types
    that are relevant to test the CLI in its current form.
    """

    def __init__(self):
        self.blueprints = MicroMock()
        self.deployments = MicroMock()
        self.executions = MicroMock()

    def status(self):
        return type('obj', (object,), {'status': 'running',
                                       'services': []})

    def list_blueprints(self):
        return []

    def list_deployments(self):
        return []

    def publish_blueprint(self, blueprint_path, blueprint_id='a-blueprint-id'):
        return MicroMock(id=blueprint_id)

    def delete_blueprint(self, blueprint_id):
        if not isinstance(blueprint_id, str):
            raise RuntimeError("blueprint_id should be a string")
        pass

    def create_deployment(self, blueprint_id, deployment_id):
        return MicroMock(id='a-deployment-id')

    def delete_deployment(self, deployment_id, ignore_live_nodes=False):
        if not isinstance(deployment_id, str) or not isinstance(
                ignore_live_nodes, bool):
            raise RuntimeError("bad parameters types provided")
        pass

    def execute_deployment(self, deployment_id, operation, events_handler=None,
                           timeout=900, include_logs=False, force=False):
        if operation != 'install':
            raise CosmoManagerRestCallError("operation {0} doesn't exist"
                                            .format(operation))
        return 'execution-id', None

    def cancel_execution(self, execution_id):
        return 'execution-id'

    def list_workflows(self, deployment_id):
        return {}

    def list_deployment_executions(self, deployment_id):
        return []

    def get_all_execution_events(self, execution_id, include_logs=False):
        return []

    def get_provider_context(self):
        return {
            'name': get_mock_provider_name(),
            'context': _provider_context
        }

    def post_provider_context(self, name, provider_context):
        global _provider_context
        global _provider_name
        _provider_context = provider_context
        _provider_name = name


class MicroMock(object):

    """
    A class to help ease the creation of anonymous objects
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def list(self, *args):
        return []

    def list_workflows(self, deployment_id):
        return {}
