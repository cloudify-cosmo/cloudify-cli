import os
import shutil
import tarfile
import tempfile
from contextlib import closing

from mock import MagicMock

from .. import cfy
from ... import env
from ... import utils
from ...commands import profiles
from .test_base import CliCommandTest


class ProfilesTest(CliCommandTest):
    def test_get_active_profile(self):
        self.use_manager()
        outcome = self.invoke('profiles show-current')
        self.assertIn('manager_ip', outcome.logs)
        self.assertIn('10.10.1.10', outcome.logs)
        self.assertIn('rest_port', outcome.logs)
        self.assertIn('80', outcome.logs)

    def test_get_profile(self):
        self.use_manager()
        profile_output = profiles._get_profile('10.10.1.10')
        self.assertDictContainsSubset(
            profile_output, cfy.default_manager_params)

    def test_get_profile_no_active_manager(self):
        outcome = self.invoke('profiles show-current')
        self.assertIn("You're currently working in local mode", outcome.logs)

    def test_list_profiles(self):
        self.use_manager()
        outcome = self.invoke('profiles list')
        self.assertIn('manager_ip', outcome.logs)
        self.assertIn('*10.10.1.10', outcome.logs)
        self.assertIn('rest_port', outcome.logs)
        self.assertIn('80', outcome.logs)

    def test_list_profiles_no_profiles(self):
        outcome = self.invoke('profiles list')
        self.assertIn('No profiles found.', outcome.logs)

    def test_list_profiles_no_active_manager(self):
        self.use_manager()
        self.invoke('cfy profiles use local')
        self.invoke('cfy profiles list')
        # TODO: This isn't tested right due to the logs containing
        # to much ambiguous info to check for
        # self.assertNotIn('*localhost', outcome.logs)

    def test_delete_profile(self):
        self.use_manager()
        self.assertTrue(os.path.isdir(
            os.path.join(env.PROFILES_DIR, '10.10.1.10')))
        self.invoke('cfy profiles delete 10.10.1.10')
        self.invoke('cfy profiles list')
        # TODO: This isn't tested right due to the logs containing
        # to much ambiguous info to check for
        # self.assertNotIn('localhost', outcome.logs)

    def test_delete_non_existing_profile(self):
        manager_ip = '10.10.1.10'
        outcome = self.invoke('cfy profiles delete {0}'.format(manager_ip))
        self.assertIn('Profile {0} does not exist'.format(manager_ip),
                      outcome.logs)

    def test_export_import_profiles(self):
        fd, profiles_archive = tempfile.mkstemp()
        os.close(fd)
        self.use_manager()
        try:
            self.invoke('cfy profiles export -o {0}'.format(profiles_archive))
            with closing(tarfile.open(name=profiles_archive)) as tar:
                members = [member.name for member in tar.getmembers()]
            self.assertIn('profiles/10.10.1.10/context', members)
            cfy.purge_dot_cloudify()
            self.assertFalse(os.path.isdir(env.PROFILES_DIR))
            self.invoke('cfy init')
            self.invoke('cfy profiles import {0}'.format(profiles_archive))
            self.assertTrue(os.path.isfile(
                os.path.join(env.PROFILES_DIR, '10.10.1.10', 'context')))
        finally:
            os.remove(profiles_archive)

    def test_export_profiles_with_keys(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name',
                'context': {}}
        )
        fd1, profiles_archive = tempfile.mkstemp()
        fd2, key = tempfile.mkstemp()
        os.close(fd1)
        os.close(fd2)
        with open(key, 'w') as f:
            f.write('aaa')
        self.use_manager(ssh_key_path=key)
        self.invoke('profiles list')
        try:
            self.invoke('cfy profiles export -o {0} --include-keys'.format(
                profiles_archive))
            with closing(tarfile.open(name=profiles_archive)) as tar:
                members = [member.name for member in tar.getmembers()]
            self.assertIn('profiles/10.10.1.10/context', members)
            self.assertIn('profiles/{0}/{1}.10.10.1.10.profile'.format(
                profiles.EXPORTED_KEYS_DIRNAME,
                os.path.basename(key)), members)
            cfy.purge_dot_cloudify()
            os.remove(key)
            self.assertFalse(os.path.isdir(env.PROFILES_DIR))

            # First make sure that the ssh keys message is being logged
            self.invoke('cfy init')
            outcome = self.invoke(
                'cfy profiles import {0}'
                .format(profiles_archive)
            )
            self.assertIn(
                'The profiles archive you provided contains ssh keys',
                outcome.logs
            )

            # Then actually import the profile with the keys
            cfy.purge_dot_cloudify()
            self.invoke('cfy init')
            self.invoke(
                'cfy profiles import {0} --include-keys'
                .format(profiles_archive)
            )

            self.assertTrue(os.path.isfile(
                os.path.join(env.PROFILES_DIR, '10.10.1.10', 'context')))
            self.assertTrue(os.path.isfile(key))
        finally:
            os.remove(key)
            os.remove(profiles_archive)

    def test_export_profiles_no_profiles_to_export(self):
        self.invoke(
            'cfy profiles export',
            err_str_segment='No profiles to export')

    def test_import_bad_profiles_archive(self):
        bad_profiles_dir = tempfile.mkdtemp()
        fd, bad_profiles_archive = tempfile.mkstemp()
        os.close(fd)
        utils.tar(bad_profiles_dir, bad_profiles_archive)
        try:
            self.invoke(
                'cfy profiles import {0}'.format(bad_profiles_archive),
                err_str_segment='The archive provided does not seem to be '
                'a valid Cloudify profiles archive')
        finally:
            os.remove(bad_profiles_archive)
            shutil.rmtree(bad_profiles_dir)

    def test_import_not_tar(self):
        fd, profiles_archive = tempfile.mkstemp()
        os.close(fd)
        try:
            self.invoke(
                'cfy profiles import {0}'.format(profiles_archive),
                err_str_segment='The archive provided must be a tar.gz '
                'archive')
        finally:
            os.remove(profiles_archive)

    def _test_conflict(self, variable):
        env_var = 'CLOUDIFY_{0}'.format(variable).upper()
        error_msg = 'Manager {0} is set in profile '.format(variable.title())
        temp_value = 'value'
        self.use_manager()

        # Setting the env variable should cause the invocation to fail
        os.environ[env_var] = temp_value
        self.client.blueprints.list = MagicMock(return_value=[])
        self.invoke('blueprints list', err_str_segment=error_msg)

        # Unsetting the variable in the profile should fix this
        self.invoke('profiles unset --manager-{0}'.format(variable))
        self.invoke('blueprints list')

        # Setting the variable in the profile should cause it to fail again
        self.invoke('profiles set --manager-{0} {1}'.format(
            variable, temp_value))
        self.invoke('blueprints list', err_str_segment=error_msg)

        # Finally, unsetting the env variable should fix this
        os.environ[env_var] = ''
        self.invoke('blueprints list')

    def test_conflict_manager_username(self):
        self._test_conflict('username')

    def test_conflict_manager_password(self):
        self._test_conflict('password')

    def test_conflict_manager_tenant(self):
        self._test_conflict('tenant')

    def test_set_no_args(self):
        self.invoke('profiles set',
                    'You must supply at least one of the following')

    def test_unset_no_args(self):
        self.invoke('profiles unset',
                    'You must choose at least one of the following')

    def test_set_and_unset_combinations(self):
        self.use_manager()

        self.invoke('profiles set -u 0 -p 0 -t 0')
        self.assertEquals('0', env.profile.manager_username)
        self.assertEquals('0', env.profile.manager_password)
        self.assertEquals('0', env.profile.manager_tenant)

        self.invoke('profiles set -u 1 -p 1')
        self.assertEquals('1', env.profile.manager_username)
        self.assertEquals('1', env.profile.manager_password)
        self.assertEquals('0', env.profile.manager_tenant)

        self.invoke('profiles set -u 2 -t 2')
        self.assertEquals('2', env.profile.manager_username)
        self.assertEquals('1', env.profile.manager_password)
        self.assertEquals('2', env.profile.manager_tenant)

        self.invoke('profiles unset -t -p')
        self.assertEquals('2', env.profile.manager_username)
        self.assertEquals(None, env.profile.manager_password)
        self.assertEquals(None, env.profile.manager_tenant)

        self.invoke('profiles set -t 3')
        self.assertEquals('2', env.profile.manager_username)
        self.assertEquals(None, env.profile.manager_password)
        self.assertEquals('3', env.profile.manager_tenant)

        self.invoke('profiles unset -u')
        self.assertEquals(None, env.profile.manager_username)
        self.assertEquals(None, env.profile.manager_password)
        self.assertEquals('3', env.profile.manager_tenant)

        self.invoke('profiles set -u 7 -p blah -t -3')
        self.assertEquals('7', env.profile.manager_username)
        self.assertEquals('blah', env.profile.manager_password)
        self.assertEquals('-3', env.profile.manager_tenant)

        self.invoke('profiles unset -u -p -t')
        self.assertEquals(None, env.profile.manager_username)
        self.assertEquals(None, env.profile.manager_password)
        self.assertEquals(None, env.profile.manager_tenant)
