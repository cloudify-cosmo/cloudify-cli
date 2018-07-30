import os
import shutil
import tarfile
import tempfile
from contextlib import closing

from mock import MagicMock, patch

from .. import cfy
from ... import env
from ... import utils
from ...commands import profiles
from .mocks import MockListResponse
from .test_base import CliCommandTest


class ProfilesTest(CliCommandTest):
    def test_profiles_uninitialized_env(self):
        cfy.purge_dot_cloudify()
        result = self.invoke('profiles list')
        self.assertIn('No profiles found', result.output)

    def test_get_active_profile(self):
        self.use_manager()
        outcome = self.invoke('profiles show-current')
        self.assertIn('manager_ip', outcome.output)
        self.assertIn('10.10.1.10', outcome.output)
        self.assertIn('rest_port', outcome.output)
        self.assertIn('80', outcome.output)

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
        self.assertIn('manager_ip', outcome.output)
        self.assertIn('*10.10.1.10', outcome.output)
        self.assertIn('rest_port', outcome.output)
        self.assertIn('80', outcome.output)

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

    def test_export_env_not_initialized(self):
        cfy.purge_dot_cloudify()
        self.invoke(
            'cfy profiles export',
            err_str_segment='No profiles to export')

    def test_import_env_not_initialized(self):
        fd, profiles_archive = tempfile.mkstemp()
        os.close(fd)
        self.use_manager()
        try:
            self.invoke('cfy profiles export -o {0}'.format(profiles_archive))
            cfy.purge_dot_cloudify()
            self.invoke('cfy profiles import {0}'.format(profiles_archive))
        finally:
            os.remove(profiles_archive)

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
        self.client.blueprints.list = MagicMock(
            return_value=MockListResponse()
        )
        self.invoke('blueprints list', err_str_segment=error_msg)

        # Unsetting the variable in the profile should fix this
        self.invoke('profiles unset --manager-{0} '
                    '--skip-credentials-validation'.format(variable))
        self.invoke('blueprints list')

        # Setting the variable in the profile should cause it to fail again
        self.invoke('profiles set --manager-{0} {1} '
                    '--skip-credentials-validation'.format(
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

        self.invoke('profiles set -u 0 -p 0 -t 0 '
                    '--skip-credentials-validation')
        self.assertEquals('0', env.profile.manager_username)
        self.assertEquals('0', env.profile.manager_password)
        self.assertEquals('0', env.profile.manager_tenant)

        self.invoke('profiles set -u 1 -p 1 --skip-credentials-validation')
        self.assertEquals('1', env.profile.manager_username)
        self.assertEquals('1', env.profile.manager_password)
        self.assertEquals('0', env.profile.manager_tenant)

        self.invoke('profiles set -u 2 -t 2 --skip-credentials-validation')
        self.assertEquals('2', env.profile.manager_username)
        self.assertEquals('1', env.profile.manager_password)
        self.assertEquals('2', env.profile.manager_tenant)

        self.invoke('profiles unset -t -p --skip-credentials-validation')
        self.assertEquals('2', env.profile.manager_username)
        self.assertEquals(None, env.profile.manager_password)
        self.assertEquals(None, env.profile.manager_tenant)

        self.invoke('profiles set -t 3 --skip-credentials-validation')
        self.assertEquals('2', env.profile.manager_username)
        self.assertEquals(None, env.profile.manager_password)
        self.assertEquals('3', env.profile.manager_tenant)

        self.invoke('profiles unset -u --skip-credentials-validation')
        self.assertEquals(None, env.profile.manager_username)
        self.assertEquals(None, env.profile.manager_password)
        self.assertEquals('3', env.profile.manager_tenant)

        self.invoke('profiles set -u 7 -p blah -t -3 '
                    '--skip-credentials-validation')
        self.assertEquals('7', env.profile.manager_username)
        self.assertEquals('blah', env.profile.manager_password)
        self.assertEquals('-3', env.profile.manager_tenant)

        self.invoke('profiles unset -u -p -t --skip-credentials-validation')
        self.assertEquals(None, env.profile.manager_username)
        self.assertEquals(None, env.profile.manager_password)
        self.assertEquals(None, env.profile.manager_tenant)

    def test_set_fails_without_skip(self):
        self.use_manager()
        self.invoke(
            'profiles set -u 0 -p 0 -t 0',
            err_str_segment="Can't use manager"
        )

    @patch('cloudify_cli.commands.profiles._validate_credentials')
    def test_set_works_without_skip(self, validate_credentials_mock):
        self.use_manager()
        self.invoke('profiles set -u 0 -p 0 -t 0 -c 0')

        validate_credentials_mock.assert_called_once_with('0', '0', '0', '0',
                                                          None, None)
        self.assertEquals('0', env.profile.manager_username)
        self.assertEquals('0', env.profile.manager_password)
        self.assertEquals('0', env.profile.manager_tenant)
        self.assertEquals('0', env.profile.rest_certificate)

    def test_cannot_set_name_local(self):
        self.use_manager()
        self.invoke('profiles set --profile-name local '
                    '--skip-credentials-validation',
                    err_str_segment='reserved')

    def test_cannot_set_taken_name(self):
        self.use_manager()
        self.invoke('profiles set --profile-name a '
                    '--skip-credentials-validation')

        self.use_manager()
        self.invoke('profiles set --profile-name a '
                    '--skip-credentials-validation',
                    err_str_segment='already exists')

    def test_set_assigns_profile_name(self):
        self.invoke('profiles set --profile-name some-profile '
                    '--skip-credentials-validation')
        self.assertEquals('some-profile', env.profile.profile_name)

    def test_profile_name_defaults_to_ip(self):
        p = env.ProfileContext()
        p.manager_ip = '1.2.3.4'
        self.assertEquals('1.2.3.4', p.profile_name)

        # pyyaml creates the object like that - skipping __init__; check that
        # this doesn't break to allow correct handling pre-profile_name
        # profiles
        p = env.ProfileContext.__new__(env.ProfileContext)
        self.assertIs(None, p.profile_name)
        p.manager_ip = '1.2.3.4'
        self.assertEquals('1.2.3.4', p.profile_name)

    @patch('cloudify_cli.commands.profiles._get_provider_context',
           return_value={})
    def test_use_defaults_ip_to_profile_name(self, *_):
        outcome = self.invoke('profiles use 1.2.3.4')
        self.assertIn('Using manager 1.2.3.4', outcome.logs)
        added_profile = env.get_profile_context('1.2.3.4')
        self.assertEqual('1.2.3.4', added_profile.profile_name)
        self.assertEqual('1.2.3.4', added_profile.manager_ip)

    @patch('cloudify_cli.commands.profiles._get_provider_context',
           return_value={})
    def test_use_sets_provided_manager_ip(self, *_):
        outcome = self.invoke('profiles use 1.2.3.4 --profile-name 5.6.7.8')
        self.assertIn('Using manager 1.2.3.4', outcome.logs)
        added_profile = env.get_profile_context('5.6.7.8')
        self.assertEqual('1.2.3.4', added_profile.manager_ip)
        self.assertEqual('5.6.7.8', added_profile.profile_name)

    @patch('cloudify_cli.commands.profiles._get_provider_context',
           return_value={})
    def test_use_cannot_update_profile(self, *_):
        self.use_manager()
        outcome = self.invoke('profiles use 10.10.1.10 -p abc')
        self.assertIn('The passed in options are ignored: manager_password',
                      outcome.logs)

    @patch('cloudify_cli.commands.profiles._get_provider_context',
           return_value={})
    def test_use_existing_only_switches(self, mock_get_context):
        self.use_manager()
        self.invoke('profiles use 10.10.1.10')
        self.assertFalse(mock_get_context.called)

    @patch('cloudify_cli.commands.profiles._get_provider_context',
           return_value={})
    def test_cluster_set_changes_cert(self, mock_get_context):
        self.use_manager()
        env.profile.cluster = [{'name': 'first'}]
        self.invoke('profiles set-cluster first --rest-certificate CERT_PATH')
        self.assertIn('cert', env.profile.cluster[0])
        self.assertEqual(env.profile.cluster[0]['cert'], 'CERT_PATH')

    @patch('cloudify_cli.commands.profiles._get_provider_context',
           return_value={})
    def test_cluster_set_nonexistent_node(self, mock_get_context):
        self.use_manager()
        env.profile.cluster = [{'name': 'first'}]
        self.invoke('profiles set-cluster second --rest-certificate CERT_PATH',
                    err_str_segment='second not found')
