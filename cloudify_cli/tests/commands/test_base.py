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
import logging
import os as utils_os
import shlex
import shutil
import pytest
import traceback

import testtools
from mock import patch, Mock, PropertyMock

from cloudify.utils import setup_logger
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.client import CLOUDIFY_TENANT_HEADER
import click.testing as clicktest
from cloudify._compat import PY2, text_type
from ... import env
from ... import utils
from ... import logger
from ...commands import init
from ... import main
from ...exceptions import CloudifyCliError
from ...logger import set_global_json_output
from ... import constants


default_manager_params = dict(
    name='10.10.1.10',
    manager_ip='10.10.1.10',
    ssh_key='key',
    ssh_user='test',
    ssh_port='22',
    provider_context={},
    rest_port=80,
    rest_protocol='http',
    rest_certificate=None,
    kerberos_env=False,
    manager_username='admin',
    manager_password='admin',
    manager_tenant=constants.DEFAULT_TENANT_NAME,
    cluster={}
)


class ClickInvocationException(Exception):
    def __init__(self,
                 message,
                 output=None,
                 logs=None,
                 exit_code=1,
                 exception=None,
                 exc_info=None):
        super(ClickInvocationException, self).__init__(message)
        self.message = message
        self.output = output
        self.logs = logs
        self.exit_code = exit_code
        self.exception = exception
        self.ex_type, self.ex_value, self.ex_tb = exc_info if exc_info else \
            (None, None, None)

    def __str__(self):
        string = '\nMESSAGE: {0}\n'.format(self.message)
        string += 'STDOUT: {0}\n'.format(self.output)
        string += 'EXIT_CODE: {0}\n'.format(self.exit_code)
        string += 'LOGS: {0}\n'.format(self.logs)
        if self.ex_type:
            exc_info_str_list = traceback.format_exception(
                self.ex_type, self.ex_value, self.ex_tb)
        else:
            exc_info_str_list = ["<None>"]

        string += 'EXC_INFO:\n{0}\n'.format(''.join(exc_info_str_list))
        return string

    __repr__ = __str__

@pytest.mark.usefixtures('class_caplog')
@pytest.mark.usefixtures('class_tmpdir')
class CliCommandTest(testtools.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger('CliCommandTest')

    def setUp(self):
        super(CliCommandTest, self).setUp()
        logdir = os.path.dirname(env.DEFAULT_LOG_FILE)

        # create log folder
        if not os.path.exists(logdir):
            os.makedirs(logdir, mode=0o700)

        self.client = CloudifyClient()

        def get_mock_rest_client(*args, **kwargs):
            if 'tenant_name' in kwargs:
                self.client._client.headers[CLOUDIFY_TENANT_HEADER] = \
                    kwargs['tenant_name']
            return self.client

        workdir = self.tmpdir / '.cloudify'
        self._patchers = [
            patch('cloudify_cli.env.get_rest_client', get_mock_rest_client),
            patch('os.getcwd', return_value=workdir),
            patch('cloudify_cli.env.CLOUDIFY_WORKDIR', workdir),
            patch('cloudify_cli.env.PROFILES_DIR',
                  os.path.join(workdir, 'profiles')),
            patch('cloudify_cli.env.ACTIVE_PROFILE',
                  os.path.join(workdir, 'active.profile')),
            patch('cloudify_cli.config.config.CLOUDIFY_CONFIG_PATH',
                  os.path.join(workdir, 'config.yaml')),
        ]
        for p in self._patchers:
            p.start()
        self.use_manager()
        set_global_json_output(False)
        self.caplog.set_level(logging.INFO)

    def tearDown(self):
        super(CliCommandTest, self).tearDown()
        self.purge_dot_cloudify()

        for p in self._patchers:
            p.stop()

        # empty log file
        if os.path.exists(env.DEFAULT_LOG_FILE):
            with open(env.DEFAULT_LOG_FILE, 'w') as f:
                f.write('')

    def _do_invoke(self, command):
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
        outcome.logs = '\n'.join(lr.message for lr in self.caplog.records)
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
            raise ClickInvocationException(
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
                self.invoke(command)
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
                self.invoke(command)
            except BaseException as e:
                if not ignore_errors:
                    raise
                self.logger.info(e.message)
            self.assertFalse(mock.called)

    def use_manager(self, **overrides):
        manager_params = default_manager_params.copy()
        manager_params.update(overrides)

        provider_context = manager_params['provider_context'] or {}
        profile = env.ProfileContext()
        profile.manager_ip = manager_params['manager_ip']
        profile.ssh_key = manager_params['ssh_key']
        profile.ssh_user = manager_params['ssh_user']
        profile.ssh_port = manager_params['ssh_port']
        profile.rest_port = manager_params['rest_port']
        profile.rest_protocol = manager_params['rest_protocol']
        profile.manager_username = manager_params['manager_username']
        profile.manager_password = manager_params['manager_password']
        profile.manager_tenant = manager_params['manager_tenant']
        profile.cluster = manager_params['cluster']
        profile.provider_context = provider_context

        profile.save()
        env.profile = profile
        init.set_config()
        env.set_active_profile(manager_params['manager_ip'])
        return profile

    def purge_dot_cloudify(self):
        dot_cloudify_dir = env.CLOUDIFY_WORKDIR
        if os.path.isdir(dot_cloudify_dir):
            shutil.rmtree(dot_cloudify_dir)

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
