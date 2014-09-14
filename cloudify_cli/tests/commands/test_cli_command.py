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


import os
import shutil
import unittest
import sys

from cloudify_cli.config.logger_config import LOG_DIR
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.tests import cli_runner
from cloudify_cli import utils
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_cli.utils import os as utils_os


TEST_DIR = '/tmp/cloudify-cli-component-tests'
TEST_WORK_DIR = TEST_DIR + "/cloudify"
TEST_PROVIDERS_DIR = TEST_DIR + "/mock-providers"
THIS_DIR = os.path.dirname(os.path.dirname(__file__))
BLUEPRINTS_DIR = os.path.join(THIS_DIR, 'resources', 'blueprints')


class CliCommandTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # copy provider to provider directory
        # this creates the directory as well
        shutil.copytree('{0}/resources/providers/mock_provider/'
                        .format(THIS_DIR), TEST_PROVIDERS_DIR)
        shutil.copy(
            '{0}/resources/providers/mock_provider_with_cloudify_prefix'
            '/cloudify_mock_provider_with_cloudify_prefix.py'
            .format(THIS_DIR), TEST_PROVIDERS_DIR
        )

        # append providers to path
        # so that its importable
        sys.path.append(TEST_PROVIDERS_DIR)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_DIR)

    def setUp(self):

        # create log folder
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)

        # create test working directory
        if not os.path.exists(TEST_WORK_DIR):
            os.makedirs(TEST_WORK_DIR)

        self.client = CloudifyClient()
        utils.get_rest_client = lambda x: self.client
        utils.get_cwd = lambda: TEST_WORK_DIR
        utils_os.getcwd = lambda: TEST_WORK_DIR

    def tearDown(self):

        # empty log file
        from cloudify_cli.config.logger_config import LOGGER
        logfile = LOGGER['handlers']['file']['filename']
        if os.path.exists(logfile):
            with open(logfile, 'w') as f:
                f.write('')

        # delete test working directory
        if os.path.exists(TEST_WORK_DIR):
            shutil.rmtree(TEST_WORK_DIR)

    def _assert_ex(self, cli_cmd, err_str_segment):
        try:
            cli_runner.run_cli(cli_cmd)
            self.fail('Expected error {0} was not raised for command {1}'
                      .format(err_str_segment, cli_cmd))
        except SystemExit, ex:
            self.assertIn(err_str_segment, str(ex))
        except CloudifyCliError, ex:
            self.assertIn(err_str_segment, str(ex))
        except CloudifyClientError, ex:
            self.assertIn(err_str_segment, str(ex))

    def _create_cosmo_wd_settings(self, settings=None):
        directory_settings = utils.CloudifyWorkingDirectorySettings()
        directory_settings.set_management_server('localhost')
        utils.delete_cloudify_working_dir_settings()
        utils.dump_cloudify_working_dir_settings(
            settings or directory_settings, update=False)

    def _read_cosmo_wd_settings(self):
        return utils.load_cloudify_working_dir_settings()
