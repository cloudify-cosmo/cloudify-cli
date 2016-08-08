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
    def test_profiles_uninitialized_env(self):
        cfy.purge_dot_cloudify()
        self.invoke(
            'profiles list',
            err_str_segment='Cloudify environment is not initialized')

    def test_get_active_profile(self):
        self.use_manager()
        outcome = self.invoke('profiles get-active')
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
        outcome = self.invoke('profiles get-active')
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
        self.invoke('cfy use local')
        outcome = self.invoke('cfy profiles list')
        # self.assertNotIn('*localhost', outcome.logs)

    def test_delete_profile(self):
        self.use_manager()
        self.assertTrue(os.path.isdir(
            os.path.join(env.PROFILES_DIR, '10.10.1.10')))
        self.invoke('cfy profiles delete 10.10.1.10')
        outcome = self.invoke('cfy profiles list')
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
            err_str_segment='Cloudify environment is not initialized')

    def test_import_env_not_initialized(self):
        fd, profiles_archive = tempfile.mkstemp()
        os.close(fd)
        self.use_manager()
        try:
            self.invoke('cfy profiles export -o {0}'.format(profiles_archive))
            cfy.purge_dot_cloudify()
            self.invoke(
                'cfy profiles import {0}'.format(profiles_archive),
                err_str_segment='Cloudify environment is not initialized')
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
