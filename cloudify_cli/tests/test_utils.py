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

from cloudify_cli import utils
from cloudify_cli import constants
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.utils import CloudifyWorkingDirectorySettings


TEST_DIR = '/tmp/cloudify-cli-unit-tests'
TEST_WORK_DIR = TEST_DIR + '/cloudify'


class CliUtilsUnitTests(unittest.TestCase):

    """
    Unit tests for methods in utils.py
    """

    @classmethod
    def setUpClass(cls):
        os.mkdir(TEST_DIR)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_DIR)

    def setUp(self):
        utils.get_cwd = lambda: TEST_WORK_DIR
        os.mkdir(TEST_WORK_DIR)
        os.chdir(TEST_WORK_DIR)

    def tearDown(self):
        shutil.rmtree(TEST_WORK_DIR)

    def test_get_existing_init_path_from_inner_dir(self):

        # first create the init
        init_path = os.path.join(utils.get_cwd(),
                                 constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
        os.mkdir(init_path)

        # switch working directory to inner one
        new_cwd = os.path.join(utils.get_cwd(),
                               'test_get_existing_init_path')
        os.mkdir(new_cwd)
        utils.get_cwd = lambda: new_cwd

        self.assertEqual(utils.get_init_path(), init_path)

    def test_get_existing_init_path_from_init_dir(self):

        # first create the init
        init_path = os.path.join(utils.get_cwd(),
                                 constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
        os.mkdir(init_path)

        self.assertEqual(utils.get_init_path(), init_path)

    def test_get_init_path_from_outside_dir(self):

        # first create the init
        init_path = os.path.join(utils.get_cwd(),
                                 constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
        os.mkdir(init_path)

        # switch working directory to outer one
        new_cwd = os.path.dirname(os.path.dirname(init_path))
        utils.get_cwd = lambda: new_cwd

        self.assertRaises(CloudifyCliError, utils.get_init_path)

    def test_dump_cosmo_working_dir_settings_update(self):

        self.assertRaises(CloudifyCliError,
                          utils.dump_cloudify_working_dir_settings,
                          cosmo_wd_settings=CloudifyWorkingDirectorySettings(),
                          update=True)

    def test_dump_cosmo_working_dir_settings_create(self):

        directory_settings = CloudifyWorkingDirectorySettings()
        utils.dump_cloudify_working_dir_settings(
            cosmo_wd_settings=directory_settings,
            update=False)

        utils.load_cloudify_working_dir_settings()
