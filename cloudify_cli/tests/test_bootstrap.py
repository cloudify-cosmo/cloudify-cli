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
import unittest
import tempfile
import filecmp

from cloudify_cli import constants
from cloudify_cli import utils
from cloudify_cli.bootstrap import bootstrap
from cloudify_cli.bootstrap import tasks
from cloudify.exceptions import NonRecoverableError

TEST_DIR = '/tmp/cloudify-cli-unit-tests'


class CliBootstrapUnitTests(unittest.TestCase):
    """Unit tests for functions in bootstrap/bootstrap.py"""

    def setUp(self):
        os.makedirs(TEST_DIR)
        test_workdir = tempfile.mkdtemp(dir=TEST_DIR)
        utils.get_cwd = lambda: test_workdir
        self.bootstrap_dir = os.path.join(test_workdir, '.cloudify',
                                          'bootstrap')
        self.manager_dir = os.path.join(self.bootstrap_dir, 'manager')
        os.makedirs(self.bootstrap_dir)

        os.chdir(test_workdir)

    def tearDown(self):
        shutil.rmtree(TEST_DIR)

    def test_manager_deployment_dump(self, remove_deployment=True):
        manager1_original_dir = os.path.join(
            os.path.dirname(__file__),
            'resources', 'storage', 'manager1')
        if not os.path.exists(self.manager_dir):
            shutil.copytree(manager1_original_dir, self.manager_dir)
        result = bootstrap.dump_manager_deployment()
        if remove_deployment:
            shutil.rmtree(self.manager_dir)
            self.assertTrue(
                bootstrap.read_manager_deployment_dump_if_needed(result))
        else:
            self.assertFalse(
                bootstrap.read_manager_deployment_dump_if_needed(result))
        comparison = filecmp.dircmp(manager1_original_dir,
                                    self.manager_dir)
        self.assertIn('dir1', comparison.common)
        self.assertIn('dir2', comparison.common)
        self.assertIn('file1', comparison.common)
        self.assertIn('file2', comparison.common)
        self.assertEqual(comparison.common_funny, [])
        self.assertEqual(comparison.diff_files, [])
        self.assertEqual(comparison.funny_files, [])
        self.assertEqual(comparison.left_only, [])
        self.assertEqual(comparison.right_only, [])

    def test_manager_deployment_dump_read_empty(self):
        self.assertFalse(
            bootstrap.read_manager_deployment_dump_if_needed(''))
        self.assertFalse(os.path.exists(self.manager_dir))

    def test_manager_deployment_dump_read_already_exists(self):
        self.test_manager_deployment_dump(remove_deployment=False)

    def test_creation_validation_empty_docker_dict(self):
        packages = {
            "docker": {}
        }
        try:
            tasks.creation_validation(packages)
        except NonRecoverableError as ex:
            self.assertIn(
                '"docker" must be a non-empty dictionary property under '
                '"cloudify_packages"', ex.message)

    def test_creation_validation_no_docker(self):
        packages = {
        }
        try:
            tasks.creation_validation(packages)
        except NonRecoverableError as ex:
            self.assertIn(
                '"docker" must be a non-empty dictionary property under '
                '"cloudify_packages"', ex.message)

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
        self.assertIn('rm -rf {0}/* && dpkg -i {1}/*.deb && '
                      'mv {1}/*.tar.gz {0}'.format(
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
        self.assertIn('mv {1}/*.tar.gz {0}'.format(
            agents_dest_dir, agents_pkg_path), command)

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
        self.assertIn('rm -rf {0}/* && dpkg -i {1}/*.deb'.format(
            agents_dest_dir, agents_pkg_path), command)
