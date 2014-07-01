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

from cloudify_rest_client.exceptions import CloudifyClientError
import datetime

_provider_context = {}
_provider_name = 'mock_provider'


def get_mock_provider_name():
    return _provider_name


class MockCloudifyClient(object):

    """
    A mock of the rest client, containing only the methods and object types
    that are relevant to test the CLI in its current form.
    """

    def __init__(self):
        self.blueprints = MicroMock()
        self.deployments = DeploymentsMock()
        self.executions = ExecutionsMock()
        self.events = EventsMock()
        self.manager = ManagerMock()


class MicroMock(object):

    """
    A class to help ease the creation of anonymous objects
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.id = 'id'
        self.status = 'terminated'
        self.error = None

    def create(self, blueprint_id, deployment_id):
        return MicroMock(id='a-deployment-id')

    def list(self, *args):
        return []

    def delete(self, *args, **kwargs):
        pass

    def upload(self, *args, **kwargs):
        return MicroMock()

    def execute(self, deployment_id, operation, parameters=None,
                allow_custom_parameters=False, force=False):
        if operation != 'install':
            raise CloudifyClientError("operation {0} doesn't exist"
                                      .format(operation), 400)
        return MicroMock()

    def get(self, id):
        return []


class EventsMock(object):

    def get(self,
            execution_id,
            from_event=0,
            batch_size=100,
            include_logs=False):
        return [], 0


class ManagerMock(object):

    def get_status(self):
        return {
            'status': 'running',
            'services': []
        }

    def get_context(self):
        return {
            'name': get_mock_provider_name(),
            'context': _provider_context
        }

    def create_context(self, name, provider_context):
        global _provider_context
        global _provider_name
        _provider_context = provider_context
        _provider_name = name


class ExecutionsMock(object):

    def get(self, id):
        return DictWithProperties({
            'status': 'terminated',
            'workflow_id': 'mock_wf',
            'deployment_id': 'deployment-id',
            'blueprint_id': 'blueprint-id',
            'error': '',
            'id': id,
            'created_at': datetime.datetime.now(),
            'parameters': {}
        })

    def cancel(self, id, force=False):
        pass

    def list(self, deployment_id):
        return []


class DeploymentsMock(MicroMock):

    def __init__(self, **kwargs):
        super(DeploymentsMock, self).__init__(**kwargs)
        self.blueprint_id = 'mock_blueprint_id'
        self.workflows = [
            DictWithProperties({
                'created_at': None,
                'name': 'mock_workflow',
                'parameters': [
                    {'test-key': 'test-value'},
                    'test-mandatory-key',
                    {
                        'test-nested-key': {
                            'key': 'val'
                        }
                    }
                ]
            })
        ]

    def get(self, id):
        if id == 'nonexistent-dep':
            raise CloudifyClientError("deployment {0} doesn't exist"
                                      .format('nonexistent-dep'), 404)
        return self


class DictWithProperties(dict):
    """
    A helper class. the dictionary passed will be accessible via both
    standard dictionary usage (['<field_name>']) as well as
    via attributes (obj.field_name)
    """

    def __init__(self, props_dict):
        self.update(props_dict)
        self.__dict__ = props_dict
