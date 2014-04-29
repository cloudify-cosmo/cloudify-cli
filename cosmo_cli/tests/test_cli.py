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

__author__ = 'ran'

import unittest
import os
import sys
import shutil
import subprocess
from mock_cosmo_manager_rest_client import MockCosmoManagerRestClient
from cosmo_cli import cosmo_cli as cli
from cosmo_cli.cosmo_cli import CosmoCliError
from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import CosmoManagerRestCallError


TEST_DIR = '/tmp/cloudify-cli-unit-tests'
TEST_WORK_DIR = TEST_DIR + "/cloudify"
TEST_PROVIDER_DIR = TEST_DIR + "/mock-provider"
THIS_DIR = os.path.dirname(os.path.realpath(__file__))
BLUEPRINTS_DIR = os.path.join(THIS_DIR, 'blueprints')


class CliTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.mkdir(TEST_DIR)
        os.mkdir(TEST_PROVIDER_DIR)
        sys.path.append(TEST_PROVIDER_DIR)
        shutil.copy('{0}/providers/mock_provider.py'.format(THIS_DIR),
                    TEST_PROVIDER_DIR)
        shutil.copy('{0}/providers/cloudify-config.yaml'.format(THIS_DIR),
                    TEST_PROVIDER_DIR)
        shutil.copy('{0}/providers/cloudify-config.defaults.yaml'
                    .format(THIS_DIR),
                    TEST_PROVIDER_DIR)
        shutil.copy('{0}/providers/cloudify_mock_provider2.py'
                    .format(THIS_DIR),
                    TEST_PROVIDER_DIR)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_DIR)

    def setUp(self):
        os.mkdir(TEST_WORK_DIR)
        os.chdir(TEST_WORK_DIR)

    def tearDown(self):
        shutil.rmtree(TEST_WORK_DIR)

    def _assert_ex(self, cli_cmd, err_str_segment):
        try:
            self._run_cli(cli_cmd)
            self.fail('Expected error {0} was not raised for command {1}'
                      .format(err_str_segment, cli_cmd))
        except SystemExit, ex:
            self.assertTrue(err_str_segment in str(ex))
        except CosmoCliError, ex:
            self.assertTrue(err_str_segment in str(ex))

    def _run_cli(self, args_str):
        sys.argv = args_str.split()
        cli.main()

    def _create_cosmo_wd_settings(self):
        cli._dump_cosmo_working_dir_settings(
            cli.CosmoWorkingDirectorySettings())

    def _read_cosmo_wd_settings(self):
        return cli._load_cosmo_working_dir_settings()

    def _set_mock_rest_client(self):
        cli._get_rest_client =\
            lambda ip: MockCosmoManagerRestClient()

    def test_get_basic_help(self):
        with open(os.devnull, "w") as f:
            returncode = subprocess.call("cfy", stdout=f, stderr=f)
        self.assertEquals(returncode, 2)

    def test_validate_blueprint_in_cwd(self):
        prev_cwd = os.getcwd()

        try:
            os.chdir('{0}/helloworld'.format(BLUEPRINTS_DIR))
            self._create_cosmo_wd_settings()
            self._run_cli("cfy blueprints validate blueprint.yaml")
        finally:
            os.chdir(prev_cwd)

    def test_validate_bad_blueprint(self):
        self._create_cosmo_wd_settings()
        self._assert_ex("cfy blueprints validate "
                        "{0}/bad_blueprint/blueprint.yaml".format(
                            BLUEPRINTS_DIR),
                        "Failed to validate blueprint")

    def test_validate_helloworld_blueprint(self):
        self._create_cosmo_wd_settings()
        self._run_cli(
            "cfy blueprints validate {0}/helloworld/blueprint.yaml".format(
                BLUEPRINTS_DIR))

    def test_use_command(self):
        self._create_cosmo_wd_settings()
        self._run_cli("cfy use 127.0.0.1")
        cwds = self._read_cosmo_wd_settings()
        self.assertEquals("127.0.0.1", cwds.get_management_server())

    def test_use_command_no_prior_init(self):
        self._run_cli("cfy use 127.0.0.1")
        cwds = self._read_cosmo_wd_settings()
        self.assertEquals("127.0.0.1", cwds.get_management_server())

    def test_init_explicit_provider_name(self):
        self._run_cli("cfy init mock_provider -v")
        self.assertEquals(
            "mock_provider",
            self._read_cosmo_wd_settings().get_provider())

    def test_init_implicit_provider_name(self):
        # the actual provider name is "cloudify_mock_provider2"
        self._run_cli("cfy init mock_provider2 -v")
        self.assertEquals(
            "cloudify_mock_provider2",
            self._read_cosmo_wd_settings().get_provider())

    def test_init_nonexistent_provider(self):
        self._assert_ex("cfy init mock_provider3 -v",
                        "No module named mock_provider3")

    def test_init_initialized_directory(self):
        self._create_cosmo_wd_settings()
        self._assert_ex("cfy init mock_provider",
                        "Target directory is already initialized")

    def test_init_explicit_directory(self):
        self._run_cli("cfy init mock_provider -t {0} -v".format(os.getcwd()))

    def test_init_nonexistent_directory(self):
        self._assert_ex("cfy init mock_provider -t nonexistent-dir",
                        "Target directory doesn't exist")

    def test_init_existing_provider_config_no_overwrite(self):
        self._run_cli("cfy init mock_provider -v")
        os.remove('.cloudify')
        self._assert_ex(
            "cfy init mock_provider -v",
            "Target directory already contains a provider configuration file")

    def test_init_overwrite_existing_provider_config(self):
        self._run_cli("cfy init mock_provider -v")
        os.remove('.cloudify')
        self._run_cli("cfy init mock_provider -r -v")

    def test_init_overwrite_existing_provider_config_with_cloudify_file(self):
        # ensuring the init with overwrite command also works when the
        # directory already contains a ".cloudify" file
        self._run_cli("cfy init mock_provider -v")
        self._run_cli("cfy init mock_provider -r -v")

    def test_init_overwrite_on_initial_init(self):
        # simply verifying the overwrite flag doesn't break the first init
        self._run_cli("cfy init mock_provider -r -v")

    def test_no_init(self):
        self._assert_ex("cfy bootstrap",
                        'You must first initialize by running the command '
                        '"cfy init"')

    def test_verbose_flag(self):
        self._run_cli("cfy init mock_provider -r -v")

    def test_bootstrap(self):
        self._run_cli("cfy init cloudify_mock_provider2 -v")
        self._run_cli("cfy bootstrap -v")
        settings = self._read_cosmo_wd_settings()
        self.assertEquals("10.0.0.2", settings.get_management_server())
        self.assertEquals('value', settings.get_provider_context()['key'])

        from cosmo_cli.tests.mock_cosmo_manager_rest_client import \
            _provider_context, _provider_name
        self.assertEquals('cloudify_mock_provider2', _provider_name)
        self.assertEquals('value', _provider_context['key'])

        # restore global state /:
        self._run_cli("cfy init mock_provider -v -r")
        self._run_cli("cfy bootstrap -v")

    def test_bootstrap_explicit_config_file(self):
        # note the mock providers don't actually try to read the file;
        # this test merely ensures such a flag is accepted by the CLI.
        self._run_cli("cfy init cloudify_mock_provider2 -v")
        self._run_cli("cfy bootstrap -c cloudify-config.yaml -v")
        self.assertEquals(
            "10.0.0.2",
            self._read_cosmo_wd_settings().get_management_server())

    def test_teardown_no_force(self):
        self._set_mock_rest_client()
        self._run_cli("cfy init mock_provider -v")
        self._assert_ex("cfy teardown -t 10.0.0.1",
                        "This action requires additional confirmation.")

    def test_teardown_parameters(self):
        self._set_mock_rest_client()
        self._run_cli("cfy init mock_provider -v")
        self._run_cli("cfy teardown -t 10.0.0.1 -f --ignore-validation "
                      "--ignore-deployments -c cloudify-config.yaml")

    def test_teardown_force_deployments(self):
        rest_client = MockCosmoManagerRestClient()
        rest_client.list_deployments = lambda: [{}]
        cli._get_rest_client = \
            lambda ip: rest_client
        self._run_cli("cfy init mock_provider -v")
        self._assert_ex("cfy teardown -t 10.0.0.1 -f --ignore-validation "
                        "-c cloudify-config.yaml -v",
                        "has active deployments")

    def test_teardown_force(self):
        self._set_mock_rest_client()
        self._run_cli("cfy init mock_provider -v")
        self._run_cli("cfy use 10.0.0.1")
        self._run_cli("cfy teardown -f -v")
        # the teardown should have cleared the current target management server
        self.assertEquals(
            None,
            self._read_cosmo_wd_settings().get_management_server())

    def test_teardown_force_explicit_management_server(self):
        self._set_mock_rest_client()
        self._run_cli("cfy init mock_provider -v")
        self._run_cli("cfy use 10.0.0.1")
        self._run_cli("cfy teardown -t 10.0.0.2 -f")
        self.assertEquals(
            "10.0.0.1",
            self._read_cosmo_wd_settings().get_management_server())

    def test_no_management_server_defined(self):
        # running a command which requires a target management server without
        # first calling "cfy use" or providing a target server explicitly
        self._set_mock_rest_client()
        self._run_cli("cfy init mock_provider -v")
        self._assert_ex("cfy teardown -f",
                        "Must either first run 'cfy use' command")

    def test_provider_exception(self):
        # verifying that exceptions thrown from providers are converted to
        # CosmoCliError and retain the original error message
        self._set_mock_rest_client()
        self._run_cli("cfy init cloudify_mock_provider2 -v")

        from cosmo_cli.tests import mock_cosmo_manager_rest_client
        original = mock_cosmo_manager_rest_client.get_mock_provider_name
        mock_cosmo_manager_rest_client.get_mock_provider_name = \
            lambda: 'cloudify_mock_provider2'
        try:
                self._assert_ex("cfy teardown -t 10.0.0.1 -f",
                                "cloudify_mock_provider2 teardown exception")
        finally:
            mock_cosmo_manager_rest_client.get_mock_provider_name = original

    def test_status_command_no_rest_service(self):
        self._create_cosmo_wd_settings()
        self.assertFalse(self._run_cli("cfy status -t 127.0.0.1"))

    def test_status_command(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy status -t 127.0.0.1")

    def test_blueprints_list(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy blueprints list -t 127.0.0.1")

    def test_blueprints_delete(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy blueprints delete -b a-blueprint-id -t 127.0.0.1")
        self._run_cli("cfy blueprints delete --blueprint-id a-blueprint-id "
                      "-t 127.0.0.1")

    def test_blueprints_upload_nonexistent_file(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._assert_ex(
            "cfy blueprints upload nonexistent-file -t 127.0.0.1",
            "Path to blueprint doesn't exist")

    def test_blueprints_upload(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy use 127.0.0.1")
        self._run_cli("cfy blueprints upload {0}/helloworld/blueprint.yaml"
                      .format(BLUEPRINTS_DIR))

    def test_blueprints_upload_override_id(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy use 127.0.0.1")
        self._run_cli("cfy blueprints upload {0}/helloworld/blueprint.yaml "
                      "-b my_blueprint_id"
                      .format(BLUEPRINTS_DIR))
        self._run_cli("cfy blueprints upload {0}/helloworld/blueprint.yaml "
                      "--blueprint-id my_blueprint_id2"
                      .format(BLUEPRINTS_DIR))
        self._run_cli("cfy blueprints upload {0}/helloworld/blueprint.yaml "
                      "-b my_blueprint_id".format(BLUEPRINTS_DIR))

    def test_workflows_list(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy workflows list -d a-deployment-id -t 127.0.0.1")
        self._run_cli("cfy workflows list --deployment-id a-deployment-id "
                      "-t 127.0.0.1")

    def test_deployment_create(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy deployments create -b a-blueprint-id -t 127.0.0.1"
                      " -d deployment")
        self._run_cli("cfy deployments create --blueprint-id a-blueprint-id "
                      "-t 127.0.0.1 --deployment-id deployment2")

    def test_deployments_execute(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy use 127.0.0.1")
        self._run_cli("cfy deployments execute install -d a-deployment-id "
                      "--timeout 50")
        self._run_cli("cfy deployments execute install "
                      "--deployment-id a-deployment-id")
        self._run_cli("cfy deployments execute install -d dep-id --force")

    def test_deployments_list(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        # test with explicit target
        self._run_cli('cfy deployments list -t 127.0.0.1')
        self._run_cli('cfy use 127.0.0.1')
        # test with -b and -v
        self._run_cli('cfy deployments list -b b1 -v')
        # test with --blueprint-id
        self._run_cli('cfy deployments list --blueprint-id b1')

    def test_deployments_execute_nonexistent_operation(self):
        # verifying that the CLI allows for arbitrary operation names,
        # while also ensuring correct error-handling of nonexistent
        # operations
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy use 127.0.0.1")

        expected_error = "operation nonexistent-operation doesn't exist"
        command = "cfy deployments execute nonexistent-operation " \
                  "-d a-deployment-id"
        try:
            self._run_cli(command)
            self.fail('Expected error {0} was not raised for command {1}'
                      .format(expected_error, command))
        except CosmoManagerRestCallError, ex:
            self.assertTrue(expected_error in str(ex))

    def test_executions_list(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy executions list -d deployment-id -t 127.0.0.1")
        self._run_cli("cfy executions list "
                      "--deployment-id deployment-id -s -t 127.0.0.1")

    def test_executions_cancel(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy use 127.0.0.1")
        self._run_cli("cfy executions cancel -e e_id -v")
        self._run_cli("cfy executions cancel --execution-id e_id -t 127.0.0.1")

    def test_events(self):
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy events --execution-id execution-id -t 127.0.0.1")
        self._set_mock_rest_client()
        self._run_cli("cfy events --e execution-id -t 127.0.0.1")
        self._set_mock_rest_client()
        self._create_cosmo_wd_settings()
        self._run_cli("cfy events --include-logs --execution-id execution-id "
                      "-t 127.0.0.1")
