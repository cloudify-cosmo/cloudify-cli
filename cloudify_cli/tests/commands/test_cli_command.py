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
from mock import patch

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify.utils import setup_default_logger


from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.tests import cli_runner
from cloudify_cli import utils
from cloudify_cli.utils import os as utils_os
from cloudify_cli.utils import DEFAULT_LOG_FILE


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

        cls.logger = setup_default_logger('CliCommandTest')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_DIR)

    def setUp(self):

        logdir = os.path.dirname(DEFAULT_LOG_FILE)

        # create log folder
        if not os.path.exists(logdir):
            os.makedirs(logdir)

        # create test working directory
        if not os.path.exists(TEST_WORK_DIR):
            os.makedirs(TEST_WORK_DIR)

        self.client = CloudifyClient()

        def get_mock_rest_client(manager_ip=None, rest_port=None):
            return self.client

        utils.get_rest_client = get_mock_rest_client
        utils.get_cwd = lambda: TEST_WORK_DIR
        utils_os.getcwd = lambda: TEST_WORK_DIR

    def tearDown(self):

        # empty log file
        if os.path.exists(DEFAULT_LOG_FILE):
            with open(DEFAULT_LOG_FILE, 'w') as f:
                f.write('')

        # delete test working directory
        if os.path.exists(TEST_WORK_DIR):
            shutil.rmtree(TEST_WORK_DIR)

    def _assert_ex(self,
                   cli_cmd,
                   err_str_segment,
                   possible_solutions=None):

        def _assert():
            self.assertIn(err_str_segment, str(ex))
            if possible_solutions:
                if hasattr(ex, 'possible_solutions'):
                    self.assertEqual(ex.possible_solutions,
                                     possible_solutions)
                else:
                    self.fail('Exception should have '
                              'declared possible solutions')

        try:
            cli_runner.run_cli(cli_cmd)
            self.fail('Expected error {0} was not raised for command {1}'
                      .format(err_str_segment, cli_cmd))
        except SystemExit, ex:
            _assert()
        except CloudifyCliError, ex:
            _assert()
        except CloudifyClientError, ex:
            _assert()
        except ValueError, ex:
            _assert()
        except IOError, ex:
            _assert()
        except ImportError as ex:
            _assert()

    def assert_method_called(self,
                             cli_command,
                             module,
                             function_name,
                             kwargs):
        with patch.object(module, function_name) as mock:
            try:
                cli_runner.run_cli(cli_command)
            except BaseException as e:
                self.logger.info(e.message)
            mock.assert_called_with(**kwargs)

    def _create_cosmo_wd_settings(self, settings=None):
        directory_settings = utils.CloudifyWorkingDirectorySettings()
        directory_settings.set_management_server('localhost')
        utils.delete_cloudify_working_dir_settings()
        utils.dump_cloudify_working_dir_settings(
            settings or directory_settings, update=False)
        utils.dump_configuration_file()

    def _read_cosmo_wd_settings(self):
        return utils.load_cloudify_working_dir_settings()
