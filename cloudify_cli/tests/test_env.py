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

import os
import shutil
import testtools

from .. import env
from ..exceptions import CloudifyCliError

from . import cfy


TEST_DIR = '/tmp/cloudify-cli-unit-tests'
TEST_WORK_DIR = TEST_DIR + '/cloudify'


class CliEnvTests(testtools.TestCase):

    @classmethod
    def setUpClass(cls):
        env.CLOUDIFY_WORKDIR = '/tmp/.cloudify-test'
        env.CLOUDIFY_CONFIG_PATH = os.path.join(
            env.CLOUDIFY_WORKDIR, 'config.yaml')
        env.PROFILES_DIR = os.path.join(
            env.CLOUDIFY_WORKDIR, 'profiles')
        env.ACTIVE_PRO_FILE = os.path.join(
            env.CLOUDIFY_WORKDIR, 'active.profile')

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(env.CLOUDIFY_WORKDIR):
            # shutil.rmtree(env.CLOUDIFY_WORKDIR)
            pass

    def setUp(self):
        super(CliEnvTests, self).setUp()
        cfy.invoke('init -r')

    def tearDown(self):
        super(CliEnvTests, self).tearDown()
        if os.path.isdir(env.CLOUDIFY_WORKDIR):
            shutil.rmtree(env.CLOUDIFY_WORKDIR)

    def _make_mock_profile(self, profile_name='10.10.1.10'):
        profile_path = os.path.join(env.PROFILES_DIR, profile_name)
        os.makedirs(profile_path)
        with open(os.path.join(profile_path, 'context'), 'w') as profile:
            profile.write('nothing_for_now')
        return profile_path

    def _set_manager(self):
        env.update_profile_context(
            management_ip='10.10.1.10',
            management_user='test',
            management_key='~/.my_key',
            management_port='22',
            rest_port='80',
            rest_protocol='http',
            provider_context='abc')

    def test_delete_profile(self):
        profile_path = self._make_mock_profile()
        env.delete_profile('10.10.1.10')
        self.assertFalse(os.path.isdir(profile_path))

    def test_delete_non_existing_profile(self):
        profile = 'non-existing-profile'
        ex = self.assertRaises(
            CloudifyCliError,
            env.delete_profile,
            profile_name=profile)
        self.assertEqual(
            'Profile {0} does not exist'.format(profile),
            str(ex))

    def test_profile_exists(self):
        self.assertFalse(env.is_profile_exists('non-existing-profile'))

    def test_profile_does_not_exist(self):
        self._make_mock_profile()
        self.assertTrue(env.is_profile_exists('10.10.1.10'))

    def test_assert_profile_exists(self):
        self._make_mock_profile()
        env.assert_profile_exists('10.10.1.10')

    def test_assert_non_existing_profile_exists(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.assert_profile_exists,
            profile_name='non-existing-profile')
        self.assertIn(
            'Profile {0} does not exist'.format('non-existing-profile'),
            str(ex))

    def test_set_active_profile(self):
        env.set_active_profile('10.10.1.10')
        with open(env.ACTIVE_PRO_FILE) as active_profile:
            self.assertEqual(active_profile.read(), '10.10.1.10')

    def test_get_active_profile(self):
        self.assertEqual(env.get_active_profile(), 'local')

    def test_assert_manager_not_active(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.assert_manager_active)
        self.assertIn(
            'This command is only available when using a manager',
            str(ex))

    def test_assert_manager_is_active(self):
        self._set_manager()
        env.assert_manager_active()

    def test_assert_manager_is_active_not_init(self):
        # The environment is not even initialized
        # so it should return that a manager isn't active.
        shutil.rmtree(env.CLOUDIFY_WORKDIR)
        self.assertFalse(env.is_manager_active())

    def test_assert_local_is_active(self):
        self._set_manager()
        ex = self.assertRaises(
            CloudifyCliError,
            env.assert_local_active)
        self.assertIn(
            'This command is not available when using a manager',
            str(ex))

    def test_assert_local_not_active(self):
        env.assert_local_active()

    def test_manager_not_active(self):
        self.assertFalse(env.is_manager_active())

    def test_manager_is_active(self):
        self._set_manager()
        self.assertTrue(env.is_manager_active())

    def test_get_profile_context(self):
        self._set_manager()
        context = env.get_profile_context()
        self.assertTrue(hasattr(context, 'get_management_server'))
        self.assertEqual(context.get_management_server(), '10.10.1.10')

    def test_get_profile_context_for_local(self):
        context = env.get_profile_context()
        self.assertIsNone(context)

    def test_get_context_path(self):
        self._set_manager()
        context_path = env.get_context_path()
        self.assertEqual(
            context_path,
            os.path.join(env.PROFILES_DIR, '10.10.1.10', 'context'))

    def test_fail_get_context_for_local_profile(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.get_context_path)
        self.assertEqual('Local profile does not contain context', str(ex))

    def test_fail_get_context_not_initalized(self):
        shutil.rmtree(env.CLOUDIFY_WORKDIR)
        ex = self.assertRaises(
            CloudifyCliError,
            env.get_context_path)
        self.assertEqual('Profile directory does not exist', str(ex))

    def test_get_profile_dir(self):
        self._set_manager()
        profile_dir = env.get_init_path()
        self.assertEqual(
            profile_dir,
            os.path.join(env.PROFILES_DIR, '10.10.1.10'))
        self.assertTrue(os.path.isdir(profile_dir))

    def test_get_non_existing_profile_dir(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.get_init_path)
        self.assertEqual('Profile directory does not exist', str(ex))

    def test_set_cfy_config(self):
        shutil.rmtree(env.CLOUDIFY_WORKDIR)
        os.makedirs(env.CLOUDIFY_WORKDIR)
        self.assertFalse(os.path.isfile(
            os.path.join(env.CLOUDIFY_WORKDIR, 'config.yaml')))
        env.set_cfy_config()
        self.assertTrue(os.path.isfile(
            os.path.join(env.CLOUDIFY_WORKDIR, 'config.yaml')))

    def test_set_empty_profile_context(self):
        env.set_profile_context(profile_name='10.10.1.10')
        context = env.get_profile_context('10.10.1.10')
        self.assertEqual(context.get_management_server(), None)

    def test_set_profile_context_with_settings(self):
        settings = env.ProfileContext()
        settings.set_management_server('10.10.1.10')
        env.set_profile_context(settings, profile_name='10.10.1.10')
        context = env.get_profile_context('10.10.1.10')
        self.assertEqual(context.get_management_server(), '10.10.1.10')

    def test_raise_uninitialized(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.raise_uninitialized)
        self.assertEqual('Cloudify environment is not initalized', str(ex))

    def test_update_profile_context(self):
        profile_data = dict(
            management_ip='10.10.1.10',
            management_key='~/.my_key',
            management_user='test_user',
            management_port=24,
            rest_port=80,
            rest_protocol='http',
            provider_context='provider_context',
            bootstrap_state=True)
        env.update_profile_context(**profile_data)
        context = env.get_profile_context('10.10.1.10')
        self.assertEqual(context.get_management_server(), '10.10.1.10')
        self.assertEqual(context.get_management_key(), '~/.my_key')
        self.assertEqual(context.get_management_user(), 'test_user')
        self.assertEqual(context.get_management_port(), 24)
        self.assertEqual(context.get_rest_port(), 80)
        self.assertEqual(context.get_rest_protocol(), 'http')
        self.assertEqual(context.get_provider_context(), 'provider_context')
        self.assertEqual(context.get_bootstrap_state(), True)

    def test_get_profile(self):
        profile_input = dict(
            management_ip='10.10.1.10',
            management_key='~/.my_key',
            management_user='test_user',
            management_port=24,
            rest_port=80,
            rest_protocol='http',
            provider_context='provider_context',
            bootstrap_state=True)
        env.update_profile_context(**profile_input)
        profile_output = env.get_profile('10.10.1.10')
        self.assertEqual(
            profile_input['management_ip'],
            profile_output['manager_ip'])
        self.assertEqual(
            profile_input['management_key'],
            profile_output['ssh_key_path'])
        self.assertEqual(
            profile_input['management_user'],
            profile_output['ssh_user'])
        self.assertEqual(
            profile_input['management_port'],
            profile_output['ssh_port'])
        self.assertEqual(
            profile_input['rest_port'],
            profile_output['rest_port'])
        self.assertEqual(
            profile_input['rest_protocol'],
            profile_output['rest_protocol'])
