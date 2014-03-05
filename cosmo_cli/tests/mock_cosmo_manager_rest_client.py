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


class MockCosmoManagerRestClient(object):
    #A mock of the rest client, containing only the methods and object types
    #that are relevant to test the CLI in its current form.

    def list_blueprints(self):
        return []

    def list_deployments(self):
        return []

    def publish_blueprint(self, blueprint_path, blueprint_id='a-blueprint-id'):
        return MicroMock(id=blueprint_id)

    def delete_blueprint(self, blueprint_id):
        pass

    def create_deployment(self, blueprint_id, deployment_id):
        return MicroMock(id='a-deployment-id')

    def execute_deployment(self, deployment_id, operation, events_handler=None,
                           timeout=900):
        if operation != 'install':
            raise CosmoManagerRestCallError("operation {0} doesn't exist"
                                            .format(operation))
        return 'execution-id', None

    def cancel_execution(self, execution_id):
        return 'execution-id'

    def list_workflows(self, deployment_id):
        return MicroMock(workflows=[])

    def list_deployment_executions(self, deployment_id):
        return []

    def get_all_execution_events(self, execution_id, include_logs=False):
        return []


class MicroMock(object):
    """A class to help ease the creation of anonymous objects"""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
