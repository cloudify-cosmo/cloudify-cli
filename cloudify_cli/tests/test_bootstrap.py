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
import filecmp
import unittest

from mock import patch

from cloudify.exceptions import NonRecoverableError

from . import cfy
from .. import utils
from .. import constants
from ..bootstrap import tasks
from ..bootstrap import bootstrap
from ..exceptions import CloudifyBootstrapError


class CliBootstrapUnitTests(unittest.TestCase):
    """Unit tests for functions in bootstrap/bootstrap.py"""

    def setUp(self):
        # TODO: create an actual non-local profile here.
        self.bootstrap_dir = os.path.join(
            utils.PROFILES_DIR, 'local', 'bootstrap')
        self.manager_dir = os.path.join(self.bootstrap_dir, 'manager')
        os.makedirs(self.bootstrap_dir)

        cfy.invoke('init -r')

    def tearDown(self):
        cfy.purge_dot_cloudify()

    def test_manager_deployment_dump(self, remove_deployment=True):
        manager1_original_dir = self._copy_manager1_dir_to_manager_dir()
        result = bootstrap.dump_manager_deployment()
        if remove_deployment:
            shutil.rmtree(self.manager_dir)
            self.assertTrue(
                bootstrap.read_manager_deployment_dump_if_needed(result))
        else:
            # simulating existing read manager deployment dump - .git folder
            # shouldn't appear there, so removing it alone
            shutil.rmtree(os.path.join(self.manager_dir, '.git'))
            self.assertFalse(
                bootstrap.read_manager_deployment_dump_if_needed(result))
        comparison = filecmp.dircmp(manager1_original_dir,
                                    self.manager_dir)
        self.assertIn('dir1', comparison.common)
        self.assertIn('dir2', comparison.common)
        self.assertIn('file1', comparison.common)
        self.assertIn('file2', comparison.common)
        self.assertEqual([], comparison.common_funny)
        self.assertEqual([], comparison.diff_files)
        self.assertEqual([], comparison.funny_files)
        self.assertEqual([], comparison.right_only)
        # .git folder is ignored when archiving manager deployment, and should
        # not appear in the new manager dir, only in the original one;
        # (however, since in the original dir it's named "dotgit" rather than
        # ".git", we check for that instead - yet neither should be in the
        # manager deployment either way)
        self.assertEqual(['dotgit'], comparison.left_only)

    def test_manager_deployment_dump_read_empty(self):
        self.assertFalse(
            bootstrap.read_manager_deployment_dump_if_needed(''))
        self.assertFalse(os.path.exists(self.manager_dir))

    def test_manager_deployment_dump_read_already_exists(self):
        self.test_manager_deployment_dump(remove_deployment=False)

    def test_validate_manager_deployment_size_success(self):
        # reusing the copying code, but actually there's no significance for
        # the directory being the "manager_dir" one; it's simply a directory
        # containing a "blueprint" (in this case, "file1")
        self._copy_manager1_dir_to_manager_dir()
        bootstrap.validate_manager_deployment_size(
            os.path.join(self.manager_dir, 'file1'))

    def test_validate_manager_deployment_size_failure(self):
        self._copy_manager1_dir_to_manager_dir()
        # setting max deployment size to be very small, so the validation fails
        with patch.object(bootstrap, 'MAX_MANAGER_DEPLOYMENT_SIZE', 10):
            self.assertRaisesRegexp(
                CloudifyBootstrapError,
                "The manager blueprint's folder is above the maximum allowed "
                "size when archived",
                bootstrap.validate_manager_deployment_size,
                blueprint_path=os.path.join(self.manager_dir, 'file1'))

    def test_validate_manager_deployment_size_ignore_gitfile_success(self):
        # this test checks that the validation of the manager deployment size
        # also ignores the .git folder
        self._copy_manager1_dir_to_manager_dir()
        # getting the archive's size when compressed with the .git folder
        # included in the archive
        with patch.object(bootstrap, 'blueprint_archive_filter_func',
                          lambda tarinfo: tarinfo):
            archive_obj = bootstrap.tar_manager_deployment()
            manager_dep_size = len(archive_obj.getvalue())
        # setting the limit to be smaller than the archive's size when
        # compressed with the .git folder included in the archive
        with patch.object(bootstrap, 'MAX_MANAGER_DEPLOYMENT_SIZE',
                          manager_dep_size - 1):
            # validation should pass as the limit is still bigger than
            # the size of the archive when the .git folder is excluded
            bootstrap.validate_manager_deployment_size(
                os.path.join(self.manager_dir, 'file1'))

    def test_ssl_configuration_without_cert_path(self):
        configurations = {
            constants.SSL_ENABLED_PROPERTY_NAME: True,
            constants.SSL_CERTIFICATE_PATH_PROPERTY_NAME: '',
            constants.SSL_PRIVATE_KEY_PROPERTY_NAME: ''
        }
        self.assertRaisesRegexp(
            NonRecoverableError,
            'SSL is enabled => certificate path must be provided',
            tasks._handle_ssl_configuration,
            configurations)

    def test_ssl_configuration_wrong_cert_path(self):
        configurations = {
            constants.SSL_ENABLED_PROPERTY_NAME: True,
            constants.SSL_CERTIFICATE_PATH_PROPERTY_NAME: 'wrong-path',
            constants.SSL_PRIVATE_KEY_PROPERTY_NAME: ''
        }
        self.assertRaisesRegexp(
            NonRecoverableError,
            'The certificate path \[wrong-path\] does not exist',
            tasks._handle_ssl_configuration,
            configurations)

    def test_ssl_configuration_without_key_path(self):
        this_dir = os.path.dirname(os.path.dirname(__file__))
        cert_path = os.path.join(this_dir, 'cert.file')
        open(cert_path, 'a+').close()
        configurations = {
            constants.SSL_ENABLED_PROPERTY_NAME: True,
            constants.SSL_CERTIFICATE_PATH_PROPERTY_NAME: cert_path,
            constants.SSL_PRIVATE_KEY_PROPERTY_NAME: ''
        }
        try:
            self.assertRaisesRegexp(
                NonRecoverableError,
                'SSL is enabled => private key path must be provided',
                tasks._handle_ssl_configuration,
                configurations)
        finally:
            os.remove(cert_path)

    def test_ssl_configuration_wrong_key_path(self):
        this_dir = os.path.dirname(os.path.dirname(__file__))
        cert_path = os.path.join(this_dir, 'cert.file')
        open(cert_path, 'a+').close()
        configurations = {
            constants.SSL_ENABLED_PROPERTY_NAME: True,
            constants.SSL_CERTIFICATE_PATH_PROPERTY_NAME: cert_path,
            constants.SSL_PRIVATE_KEY_PROPERTY_NAME: 'wrong-path'
        }
        try:
            self.assertRaisesRegexp(
                NonRecoverableError,
                'The private key path \[wrong-path\] does not exist',
                tasks._handle_ssl_configuration,
                configurations)
        finally:
            os.remove(cert_path)

    def test_get_install_agent_pkgs_cmd(self):
        agent_packages = {
            'agent_tar': 'agent.tar.gz',
            'agent_deb': 'agent.deb'
        }
        agents_pkg_path = '/tmp/work_dir'
        agents_dest_dir = '/opt/manager/resources/packages'

        command = tasks._get_install_agent_pkgs_cmd(
            agent_packages, agents_pkg_path, agents_dest_dir)

        self.assertIn('curl -O agent.tar.gz', command)
        self.assertIn('curl -O agent.deb', command)
        self.assertIn('dpkg -i {1}/*.deb && '
                      'mkdir -p {0}/agents && '
                      'mv {1}/agent.tar.gz {0}/agents/agent_tar.tar.gz'.format(
                          agents_dest_dir, agents_pkg_path), command)

    def test_get_install_agent_pkgs_cmd_tars_only(self):
        agent_packages = {
            'agent_tar1': 'agent1.tar.gz',
            'agent_tar2': 'agent2.tar.gz',
        }
        agents_pkg_path = '/tmp/work_dir'
        agents_dest_dir = '/opt/manager/resources/packages'

        command = tasks._get_install_agent_pkgs_cmd(
            agent_packages, agents_pkg_path, agents_dest_dir)

        self.assertIn('curl -O agent1.tar.gz', command)
        self.assertIn('curl -O agent2.tar.gz', command)
        self.assertIn('mv {1}/agent1.tar.gz {0}/agents/agent_tar1.tar.gz'
                      .format(agents_dest_dir, agents_pkg_path), command)
        self.assertIn('mv {1}/agent2.tar.gz {0}/agents/agent_tar2.tar.gz'
                      .format(agents_dest_dir, agents_pkg_path), command)

    def test_get_install_agent_pkgs_cmd_debs_only(self):
        agent_packages = {
            'agent_deb1': 'agent1.deb',
            'agent_deb2': 'agent2.deb',
        }
        agents_pkg_path = '/tmp/work_dir'
        agents_dest_dir = '/opt/manager/resources/packages'

        command = tasks._get_install_agent_pkgs_cmd(
            agent_packages, agents_pkg_path, agents_dest_dir)

        self.assertIn('curl -O agent1.deb', command)
        self.assertIn('curl -O agent2.deb', command)
        self.assertIn('dpkg -i {1}/*.deb'.format(
            agents_dest_dir, agents_pkg_path), command)

    def _copy_manager1_dir_to_manager_dir(self):
        manager1_original_dir = os.path.join(
            os.path.dirname(__file__),
            'resources', 'storage', 'manager1')
        shutil.copytree(manager1_original_dir, self.manager_dir)

        # renaming git folder to be under its proper name
        os.rename(os.path.join(self.manager_dir, 'dotgit'),
                  os.path.join(self.manager_dir, '.git'))

        return manager1_original_dir
