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

    def test_creation_validation_empty_server_dict(self):
        packages = {
            "server": "x"
        }
        try:
            tasks.creation_validation(packages)
        except NonRecoverableError as ex:
            self.assertIn(
                'must be a non-empty dictionary property under', ex.message)

    def test_creation_validation_empty_docker_dict(self):
        packages = {
            "docker": {}
        }
        try:
            tasks.creation_validation(packages)
        except NonRecoverableError as ex:
            self.assertIn(
                'must be a non-empty dictionary property under', ex.message)

    def test_creation_validation_no_docker_and_no_server(self):
        packages = {
        }
        try:
            tasks.creation_validation(packages)
        except NonRecoverableError as ex:
            self.assertIn(
                'must have exactly one of "server" and "docker"', ex.message)

    def test_creation_validation_docker_and_server(self):
        packages = {
            "docker": {"packages": "http://www.x.com/x.tar"},
            "server": {"packages": "http://www.x.com/x.deb"}
        }
        try:
            tasks.creation_validation(packages)
        except NonRecoverableError as ex:
            self.assertIn(
                'must have exactly one of "server" and "docker"', ex.message)
