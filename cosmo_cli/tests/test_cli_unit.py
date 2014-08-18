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

from cosmo_cli.cosmo_cli import CosmoCliError, CosmoWorkingDirectorySettings


__author__ = 'dan'

import unittest
import cosmo_cli.cosmo_cli as cli

TEST_DIR = '/tmp/cloudify-cli-unit-tests'
TEST_WORK_DIR = TEST_DIR + '/cloudify'


class CliUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.mkdir(TEST_DIR)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_DIR)

    def setUp(self):
        cli.get_cwd = lambda: TEST_WORK_DIR
        os.mkdir(TEST_WORK_DIR)
        os.chdir(TEST_WORK_DIR)

    def tearDown(self):
        shutil.rmtree(TEST_WORK_DIR)

    def test_create_event_message_prefix_with_unicode(self):

        from cosmo_cli.cosmo_cli import _create_event_message_prefix

        unicode_message = u'\u2018'

        event = {
            'context': {'deployment_id': 'deployment'},
            'message': {'text': unicode_message},
            'type': 'cloudify_log',
            'level': 'INFO',
            '@timestamp': 'NOW'
        }

        _create_event_message_prefix(event)

    def test_get_existing_init_path_from_inner_dir(self):

        from cosmo_cli.cosmo_cli import _get_init_path

        # first create the init
        init_path = os.path.join(cli.get_cwd(),
                                 cli.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
        os.mkdir(init_path)

        # switch working directory to inner one
        new_cwd = os.path.join(cli.get_cwd(), 'test_get_existing_init_path')
        os.mkdir(new_cwd)
        cli.get_cwd = lambda: new_cwd

        self.assertEqual(_get_init_path(), init_path)

    def test_get_existing_init_path_from_init_dir(self):

        from cosmo_cli.cosmo_cli import _get_init_path

        # first create the init
        init_path = os.path.join(cli.get_cwd(),
                                 cli.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
        os.mkdir(init_path)

        self.assertEqual(_get_init_path(), init_path)

    def test_get_init_path_from_outside_dir(self):

        from cosmo_cli.cosmo_cli import _get_init_path

        # first create the init
        init_path = os.path.join(cli.get_cwd(),
                                 cli.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
        os.mkdir(init_path)

        # switch working directory to outer one
        new_cwd = os.path.dirname(os.path.dirname(init_path))
        cli.get_cwd = lambda: new_cwd

        self.assertRaises(CosmoCliError, _get_init_path)

    def test_dump_cosmo_working_dir_settings_update(self):

        from cosmo_cli.cosmo_cli import _dump_cosmo_working_dir_settings

        self.assertRaises(CosmoCliError, _dump_cosmo_working_dir_settings,
                          cosmo_wd_settings=CosmoWorkingDirectorySettings(),
                          update=True)

    def test_dump_cosmo_working_dir_settings_create(self):

        from cosmo_cli.cosmo_cli import _dump_cosmo_working_dir_settings

        directory_settings = CosmoWorkingDirectorySettings()
        _dump_cosmo_working_dir_settings(
            cosmo_wd_settings=directory_settings,
            update=False)

        from cosmo_cli.cosmo_cli import _load_cosmo_working_dir_settings

        _load_cosmo_working_dir_settings()
