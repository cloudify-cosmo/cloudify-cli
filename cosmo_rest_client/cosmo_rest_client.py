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

    def execute_deployment(self, deployment_id, operation, timeout=900):
        end = time.time() + timeout

        with self._protected_call_to_server('executing deployment operation'):
            body = {
                'workflowId': operation
            }
            execution = self.deployments_api.execute(deployment_id=deployment_id, body=body)

            end_states = ('terminated', 'failed')
            while execution.status not in end_states:
                if end < time.time():
                    raise RuntimeError('Timeout executing deployment operation {0} of deployment {1}'.format(
                                       operation, deployment_id))
                time.sleep(1)
                execution = self.executions_api.getById(execution.id)
            if execution.status != 'terminated':
                raise RuntimeError('Execution of deployment operation {0} of deployment {1} failed. (status response:'
                                   ' {2})'.format(operation, deployment_id, execution.error))

    def _tar_blueprint(self, blueprint_path, tempdir):
        blueprint_name = os.path.basename(os.path.splitext(blueprint_path)[0])
        blueprint_directory = os.path.dirname(blueprint_path)
        tar_path = '{0}/{1}.tar.gz'.format(tempdir, blueprint_name)
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(blueprint_directory, arcname=os.path.basename(blueprint_directory))
        return tar_path

    @contextmanager
    def _protected_call_to_server(self, action_name):
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