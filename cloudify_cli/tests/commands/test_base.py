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

import testtools
from mock import patch, MagicMock

from cloudify.utils import setup_logger
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.maintenance import Maintenance

from .. import cfy
from ... import env
from ... import utils
from ...exceptions import CloudifyCliError


class CliCommandTest(testtools.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger('CliCommandTest')

    def setUp(self):
        super(CliCommandTest, self).setUp()
        logdir = os.path.dirname(env.DEFAULT_LOG_FILE)
        cfy.invoke('init -r')
        # create log folder
        if not os.path.exists(logdir):
            os.makedirs(logdir)

        self.client = CloudifyClient()

        def get_mock_rest_client(*args, **kwargs):
            return self.client

        self.original_utils_get_rest_client = env.get_rest_client
        env.get_rest_client = get_mock_rest_client
        self.original_utils_get_cwd = utils.get_cwd
        utils.get_cwd = lambda: env.CLOUDIFY_WORKDIR
        self.original_utils_os_getcwd = utils_os.getcwd
        utils_os.getcwd = lambda: env.CLOUDIFY_WORKDIR

    def tearDown(self):
        super(CliCommandTest, self).tearDown()
        cfy.purge_dot_cloudify()
        # remove mocks
        env.get_rest_client = self.original_utils_get_rest_client
        utils.get_cwd = self.original_utils_get_cwd = utils.get_cwd
        utils_os.getcwd = self.original_utils_os_getcwd = utils_os.getcwd

        # empty log file
        if os.path.exists(env.DEFAULT_LOG_FILE):
            with open(env.DEFAULT_LOG_FILE, 'w') as f:
                f.write('')

    # TODO: Remove should_fail
    # TODO: Consider separating
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
            # TODO: Consolidate
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
        cfy.use_manager(**default_manager_params)

    def _read_context(self):
        return env.get_profile_context()


class BaseUpgradeTest(CliCommandTest):

    def _test_not_in_maintenance(self, action):
        self.client.maintenance_mode.status = MagicMock(
            return_value=Maintenance({'status': 'deactivated'}))
        self.invoke('cfy {0} path -i private_ip=localhost'.format(action),
                    'To perform an upgrade of a manager to a newer '
                    'version, the manager must be in maintenance mode')

    def _test_no_bp(self, action):
        self.client.maintenance_mode.status = MagicMock(
            return_value=Maintenance({'status': 'active'}))
        self.invoke('cfy {0} path -i private_ip=localhost '
                    '-i ssh_key_filename=key_path -i ssh_port=22'
                    .format(action),
                    "No such file or directory: u'path'",
                    exception=IOError)

    def _test_no_private_ip(self, action):
        self.client.maintenance_mode.status = MagicMock(
            return_value=Maintenance({'status': 'active'}))
        self.invoke('cfy {0} path'.format(action),
                    'Private IP must be provided for the '
                    'upgrade/rollback process')

    def _test_no_inputs(self, action):
        self.client.maintenance_mode.status = MagicMock(
            return_value=Maintenance({'status': 'active'}))
        self.invoke('cfy {0} path --inputs inputs'.format(action),
                    'Invalid input: inputs')
