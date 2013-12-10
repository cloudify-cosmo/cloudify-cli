__author__ = 'ran'

import tempfile
import os
import time
import shutil
import tarfile

from swagger.swagger import ApiClient
from swagger.BlueprintsApi import BlueprintsApi
from swagger.ExecutionsApi import ExecutionsApi


class CosmoRestClient(object):

    def __init__(self, server_url):
        api_client = ApiClient(apiServer=server_url)
        self.blueprints_api = BlueprintsApi(api_client)
        self.executions_api = ExecutionsApi(api_client)

    def publish_blueprint(self, blueprint_path):
        tempdir = tempfile.mkdtemp()
        try:
            tar_path = self._tar_blueprint(blueprint_path, tempdir)
            application_file = os.path.basename(blueprint_path)
            blueprint_parent_dir = os.path.basename(os.path.dirname(blueprint_path))
            post_application_file = '{0}/{1}'.format(blueprint_parent_dir, application_file)

            with open(tar_path) as f:
                body = {
                    'application_file': post_application_file,
                    'application_archive': (os.path.basename(tar_path), f)
                }
                blueprint_state = self.blueprints_api.upload(body)

            return blueprint_state
        finally:
            shutil.rmtree(tempdir)

    def execute_blueprint(self, blueprint_id, operation, timeout=240):
        end = time.time() + timeout

        execution = self.blueprints_api.run(id=blueprint_id, workflowId=operation, deploymentId='')

        end_states = ('terminated', 'failed')
        while execution['status'] not in end_states:
            if end < time.time():
                raise RuntimeError('Timeout executing blueprint {0}'.format(blueprint_id))
            time.sleep(1)
            execution = self.executions_api.get(execution['id'])
        if execution['status'] != 'terminated':
            raise RuntimeError('Application execution failed. (status response: {0})'.format(execution))

    def _tar_blueprint(self, blueprint_path, tempdir):
        blueprint_name = os.path.basename(os.path.splitext(blueprint_path)[0])
        blueprint_directory = os.path.dirname(blueprint_path)
        tar_path = '{0}/{1}.tar.gz'.format(tempdir, blueprint_name)
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(blueprint_directory, arcname=os.path.basename(blueprint_directory))
        return tar_path