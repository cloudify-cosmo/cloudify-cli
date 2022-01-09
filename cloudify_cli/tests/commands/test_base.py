########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
import os
import os as utils_os
import shlex

import testtools
from testfixtures import log_capture
from mock import patch, Mock, PropertyMock

from cloudify.utils import setup_logger
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.client import CLOUDIFY_TENANT_HEADER
import click.testing as clicktest
from cloudify._compat import PY2, text_type
from .. import cfy
from ... import env
from ... import utils
from ... import logger
from ... import commands
from ... import main
from ...exceptions import CloudifyCliError
from ...logger import set_global_json_output


class CliCommandTest(testtools.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger('CliCommandTest')

    def setUp(self):
        super(CliCommandTest, self).setUp()
        logdir = os.path.dirname(env.DEFAULT_LOG_FILE)
        env.profile = env.ProfileContext()
        # cfy.invoke('init -r')
        self.use_manager()

        # create log folder
        if not os.path.exists(logdir):
            os.makedirs(logdir, mode=0o700)

        self.client = CloudifyClient()

        def get_mock_rest_client(*args, **kwargs):
            if 'tenant_name' in kwargs:
                self.client._client.headers[CLOUDIFY_TENANT_HEADER] = \
                    kwargs['tenant_name']
            return self.client

        self.original_utils_get_rest_client = env.get_rest_client
        env.get_rest_client = get_mock_rest_client
        self.original_utils_get_cwd = utils.get_cwd
        utils.get_cwd = lambda: env.CLOUDIFY_WORKDIR
        self.original_utils_os_getcwd = utils_os.getcwd
        utils_os.getcwd = lambda: env.CLOUDIFY_WORKDIR
        # reset in case a test set it
        set_global_json_output(False)

    def tearDown(self):
        super(CliCommandTest, self).tearDown()
        cfy.purge_dot_cloudify()

        env.get_rest_client = self.original_utils_get_rest_client
        utils.get_cwd = self.original_utils_get_cwd = utils.get_cwd
        utils_os.getcwd = self.original_utils_os_getcwd = utils_os.getcwd

        # empty log file
        if os.path.exists(env.DEFAULT_LOG_FILE):
            with open(env.DEFAULT_LOG_FILE, 'w') as f:
                f.write('')

    @log_capture()
    def _do_invoke(self, command, capture):
        logger.set_global_verbosity_level(verbose=logger.NO_VERBOSE)

        if PY2:
            if isinstance(command, text_type):
                command = command.encode('utf-8')
                parts = shlex.split(command)
                lexed_command = [p.decode('utf-8') for p in parts]
            else:
                lexed_command = shlex.split(command)
        else:
            lexed_command = shlex.split(command)

        # Safety measure in case someone wrote `cfy` at the beginning
        # of the command
        if lexed_command[0] == 'cfy':
            del lexed_command[0]

        runner = clicktest.CliRunner()
        _cfy = main._make_cfy()
        outcome = runner.invoke(_cfy, lexed_command)
        outcome.command = command
        logs = [text for logger_name, level, text in capture.actual()]
        outcome.logs = '\n'.join(logs)
        return outcome

    def invoke(self,
               command,
               err_str_segment=None,
               exception=CloudifyCliError,
               context=None):
        outcome = self._do_invoke(command)

        # An empty string might be passed, so it's best to check against None
        should_fail = err_str_segment is not None

        message_to_raise = None
        if should_fail and outcome.exit_code == 0:
            message_to_raise = 'Command {0} should have failed'
        elif not should_fail and outcome.exit_code != 0:
            message_to_raise = 'Command {0} should not have failed'

        if message_to_raise:
            raise cfy.ClickInvocationException(
                message_to_raise.format(outcome.command),
                output=outcome.output,
                logs=outcome.logs,
                exit_code=outcome.exit_code,
                exception=outcome.exception,
                exc_info=outcome.exc_info)

        if should_fail:
            self.assertIn(err_str_segment, str(outcome.exception))
            self.assertEqual(exception, type(outcome.exception))
        return outcome

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

    def use_manager(self, **manager_params):
        default_manager_params = cfy.default_manager_params.copy()
        default_manager_params.update(manager_params)
        return cfy.use_manager(**default_manager_params)

    def delete_current_profile(self):
        env.delete_profile(env.profile.name)

    def use_local_profile(self, **manager_params):
        env.set_active_profile('local')

    def _read_context(self):
        return env.get_profile_context()

    def mock_wait_for_blueprint_upload(self, value):
        patcher = patch(
            'cloudify_cli.utils.wait_for_blueprint_upload',
            Mock(return_value=PropertyMock(error=value))
        )
        self.addCleanup(patcher.stop)
        patcher.start()
