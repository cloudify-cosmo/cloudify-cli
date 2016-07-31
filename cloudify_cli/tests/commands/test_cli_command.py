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

from mock import patch

from cloudify.utils import setup_logger
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

from .. import cfy
from ... import cli
from ... import env
from ... import utils
from ... import exceptions
from ...utils import os as utils_os
from ...exceptions import CloudifyCliError


TEST_DIR = '/tmp/cloudify-cli-component-tests'
TEST_WORK_DIR = TEST_DIR + "/cloudify"
THIS_DIR = os.path.dirname(os.path.dirname(__file__))
BLUEPRINTS_DIR = os.path.join(THIS_DIR, 'resources', 'blueprints')
SNAPSHOTS_DIR = os.path.join(THIS_DIR, 'resources', 'snapshots')

# TODO: Test outputs
# TODO: Test profiles


class CliCommandTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger('CliCommandTest')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_DIR, ignore_errors=True)

    def setUp(self):
        logdir = os.path.dirname(env.DEFAULT_LOG_FILE)
        cfy.invoke('init -r')
        # create log folder
        if not os.path.exists(logdir):
            os.makedirs(logdir)

        # create test working directory
        if not os.path.exists(TEST_WORK_DIR):
            os.makedirs(TEST_WORK_DIR)

        self.client = CloudifyClient()

        def get_mock_rest_client(*args, **kwargs):
            return self.client

        self.original_utils_get_rest_client = env.get_rest_client
        env.get_rest_client = get_mock_rest_client
        self.original_utils_get_cwd = utils.get_cwd
        utils.get_cwd = lambda: TEST_WORK_DIR
        self.original_utils_os_getcwd = utils_os.getcwd
        utils_os.getcwd = lambda: TEST_WORK_DIR

    def tearDown(self):
        cfy.purge_dot_cloudify()
        # remove mocks
        env.get_rest_client = self.original_utils_get_rest_client
        utils.get_cwd = self.original_utils_get_cwd = utils.get_cwd
        utils_os.getcwd = self.original_utils_os_getcwd = utils_os.getcwd

        # empty log file
        if os.path.exists(env.DEFAULT_LOG_FILE):
            with open(env.DEFAULT_LOG_FILE, 'w') as f:
                f.write('')

        # delete test working directory
        if os.path.exists(TEST_WORK_DIR):
            shutil.rmtree(TEST_WORK_DIR)

    def invoke(self,
               command,
               err_str_segment=None,
               should_fail=None,
               exception=CloudifyCliError,
               context=None):

        if err_str_segment and should_fail is None:
            should_fail = True
        outcome = cfy.invoke(command, context=context)
        if should_fail and outcome.exit_code == 0:
            raise cfy.ClickInvocationException(
                'Command {0} should have failed'.format(outcome.command),
                output=outcome.output,
                logs=outcome.logs,
                exit_code=outcome.exit_code,
                exception=str(type(outcome.exception)),
                exc_info=str(outcome.exception))
        elif not should_fail and outcome.exit_code != 0:
            raise cfy.ClickInvocationException(
                'Command {0} should not have failed'.format(outcome.command),
                output=outcome.output,
                logs=outcome.logs,
                exit_code=outcome.exit_code,
                exception=str(type(outcome.exception)),
                exc_info=str(outcome.exception))
        if err_str_segment:
            self.assertIn(err_str_segment, str(outcome.exception))
            self.assertEqual(exception, type(outcome.exception))
        return outcome

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
            cfy.invoke(cli_cmd)
            self.fail('Expected error {0} was not raised for command {1}'
                      .format(err_str_segment, cli_cmd))
        except SystemExit as ex:
            _assert()
        except exceptions.CloudifyCliError as ex:
            _assert()
        except exceptions.CloudifyValidationError as ex:
            _assert()
        except CloudifyClientError as ex:
            _assert()
        except ValueError as ex:
            _assert()
        except IOError as ex:
            _assert()
        except ImportError as ex:
            _assert()

    def assert_method_called(self,
                             command,
                             module,
                             function_name,
                             args=None,
                             kwargs=None):
        args = args or []
        kwargs = kwargs or {}

        with patch.object(module, function_name) as mock:
            try:
                cfy.invoke(command)
            except BaseException as e:
                self.logger.info(e.message)
            mock.assert_called_with(*args, **kwargs)

    def assert_method_not_called(self,
                                 command,
                                 module,
                                 function_name,
                                 ignore_errors=False):
        with patch.object(module, function_name) as mock:
            try:
                cfy.invoke(command)
            except BaseException as e:
                if not ignore_errors:
                    raise
                self.logger.info(e.message)
            self.assertFalse(mock.called)

    def use_manager(self,
                    profile_name='test',
                    host='localhost',
                    key='key',
                    user='key',
                    port='22',
                    provider_context=None):

        if not provider_context:
            provider_context = dict()

        settings = env.ProfileContext()
        settings.set_manager_ip(host)
        settings.set_manager_key(key)
        settings.set_manager_user(user)
        settings.set_manager_port(port)
        settings.set_provider_context(provider_context)

        cfy.purge_profile(profile_name)
        env.set_profile_context(
            profile_name=profile_name,
            context=settings,
            update=False)
        env.set_cfy_config()
        env.set_active_profile(profile_name)
        cli._register_commands()

    def _read_context(self):
        return env.get_profile_context()
