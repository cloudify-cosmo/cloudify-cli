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

from .. import env
from .. import utils
from .. import inputs
from .. import constants
from ..logger import configure_loggers
from ..exceptions import CloudifyCliError
from ..env import CloudifyWorkingDirectorySettings


TEST_DIR = '/tmp/cloudify-cli-unit-tests'
TEST_WORK_DIR = TEST_DIR + '/cloudify'


class CliUtilsUnitTests(unittest.TestCase):
    """
    Unit tests for methods in utils.py
    """

    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)

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

        self.assertEqual(env.get_init_path(), init_path)

    def test_get_existing_init_path_from_init_dir(self):

        # first create the init
        init_path = os.path.join(utils.get_cwd(),
                                 constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
        os.mkdir(init_path)

        self.assertEqual(env.get_init_path(), init_path)

    def test_get_init_path_from_outside_dir(self):

        # first create the init
        init_path = os.path.join(utils.get_cwd(),
                                 constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
        os.mkdir(init_path)

        # switch working directory to outer one
        new_cwd = os.path.dirname(os.path.dirname(init_path))
        utils.get_cwd = lambda: new_cwd

        self.assertRaises(CloudifyCliError, env.get_context_path)

    def test_dump_cosmo_working_dir_settings_update(self):

        self.assertRaises(CloudifyCliError,
                          env.dump_cloudify_working_dir_settings,
                          cosmo_wd_settings=CloudifyWorkingDirectorySettings(),
                          update=True)

    def test_dump_cosmo_working_dir_settings_create(self):

        directory_settings = CloudifyWorkingDirectorySettings()
        env.dump_cloudify_working_dir_settings(
            cosmo_wd_settings=directory_settings,
            update=False)

        env.load_cloudify_working_dir_settings()

    def test_parsing_input_as_string(self):

        self.assertEqual(inputs.plain_string_to_dict(""), {})

        self.assertEqual(inputs.plain_string_to_dict(" "), {})

        self.assertEqual(inputs.plain_string_to_dict(";"), {})

        self.assertEqual(inputs.plain_string_to_dict(" ; "), {})

        expected_dict = dict(my_key1="my_value1", my_key2="my_value2")

        parsed_dict = inputs.plain_string_to_dict(
            "my_key1=my_value1;my_key2=my_value2")
        self.assertEqual(parsed_dict, expected_dict)

        parsed_dict = inputs.plain_string_to_dict(
            " my_key1 = my_value1 ;my_key2=my_value2; ")
        self.assertEqual(parsed_dict, expected_dict)

        parsed_dict = inputs.plain_string_to_dict(
            " my_key1 = my_value1 ;my_key2=my_value2; ")
        self.assertEqual(parsed_dict, expected_dict)

        expected_dict = dict(my_key1="")
        parsed_dict = inputs.plain_string_to_dict(" my_key1=")
        self.assertEqual(parsed_dict, expected_dict)

        parsed_dict = inputs.plain_string_to_dict(" my_key1=;")
        self.assertEqual(parsed_dict, expected_dict)

        expected_dict = dict(my_key1="my_value1",
                             my_key2="my_value2,my_other_value2")
        parsed_dict = inputs.plain_string_to_dict(
            " my_key1 = my_value1 ;my_key2=my_value2,my_other_value2; ")
        self.assertEqual(parsed_dict, expected_dict)

    def test_string_to_dict_error_handling(self):

        expected_err_msg = "Invalid input format: {0}, the expected " \
                           "format is: key1=value1;key2=value2"

        input_str = "my_key1"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict, input_str)

        input_str = "my_key1;"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict, input_str)

        input_str = "my_key1=my_value1;myvalue2;"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict,
                                input_str)

        input_str = "my_key1=my_value1;my_key2=myvalue2;my_other_value2;"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict,
                                input_str)

        input_str = "my_key1=my_value1;my_key2=myvalue2;my_other_value2;"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict,
                                input_str)

        input_str = "my_key1:my_value1;my_key2:my_value2"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict,
                                input_str)

    # TODO: Add several other input tests (e.g. wildcard, paths, etc)
    def test_inputs_to_dict_error_handling(self):
        configure_loggers()
        input_list = ["my_key1=my_value1;my_key2"]
        resource_name = "my_resource_name"

        expected_err_msg = \
            ("Invalid input: {0}. {1} must represent a dictionary. "
             "Valid values can be one of:\n "
             "- A path to a YAML file\n "
             "- A path to a directory containing YAML files\n "
             "- A single quoted wildcard based path ")

        self.assertRaisesRegexp(
            CloudifyCliError,
            expected_err_msg.format(input_list[0], resource_name),
            inputs.inputs_to_dict,
            input_list,
            resource_name)
