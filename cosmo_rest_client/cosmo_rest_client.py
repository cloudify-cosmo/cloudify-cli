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


class CosmoRestClient(object):

    def __init__(self, server_url):
        api_client = ApiClient(apiServer=server_url, apiKey='')
        self.blueprints_api = BlueprintsApi(api_client)
        self.executions_api = ExecutionsApi(api_client)

    def publish_blueprint(self, blueprint_path):
        tempdir = tempfile.mkdtemp()
        try:
            tar_path = self._tar_blueprint(blueprint_path, tempdir)
            application_file = os.path.basename(blueprint_path)
            blueprint_parent_dir = os.path.basename(os.path.dirname(blueprint_path))
            post_application_file = '{0}/{1}'.format(blueprint_parent_dir, application_file)

            with self._protected_call_to_server('publishing blueprint'):
                with open(tar_path, 'rb') as f:
                    blueprint_state = self.blueprints_api.upload(f.read(), post_application_file)

                return blueprint_state
        finally:
            shutil.rmtree(tempdir)

    def execute_blueprint(self, blueprint_id, operation, timeout=900):
        end = time.time() + timeout

        with self._protected_call_to_server('executing blueprint operation'):
            body = {
                'workflowId': operation
            }
            execution = self.blueprints_api.run(id=blueprint_id, body=body, deploymentId='')

            end_states = ('terminated', 'failed')
            while execution.status not in end_states:
                if end < time.time():
                    raise RuntimeError('Timeout executing blueprint {0}'.format(blueprint_id))
                time.sleep(1)
                execution = self.executions_api.get(execution.id)
            if execution.status != 'terminated':
                raise RuntimeError('Application execution failed. (status response: {0})'.format(execution))

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