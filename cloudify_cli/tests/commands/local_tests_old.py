########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import json
import os
import shutil
import tempfile
import unittest

import yaml
from cloudify_cli import utils
from dsl_parser.constants import HOST_TYPE
from .constants import BLUEPRINTS_DIR
from .test_base import CliCommandTest


@unittest.skip('Local')
class LocalTest(CliCommandTest):
    def _assert_multiple_outputs(self):
        output = self.invoke('cfy local outputs')
        self.assertIn('"input1": "new_input1"', output)
        self.assertIn('"input2": "new_input2"', output)
        self.assertIn('"input3": "new_input3"', output)

    def _generate_multiple_input_files(self):
        input_files_directory = tempfile.mkdtemp()
        with open(os.path.join(input_files_directory, 'f1.yaml'), 'w') as f:
            f.write('input1: new_input1\ninput2: new_input2')
        with open(os.path.join(input_files_directory, 'f2.yaml'), 'w') as f:
            f.write('input3: new_input3')
        return input_files_directory

    # TODO: Move it to test_env (to CliInputsTests)
    def test_local_init_with_directory_inputs(self):
        input_files_directory = self._generate_multiple_input_files()
        try:
            self._local_init(inputs=[input_files_directory])
            self._assert_multiple_outputs()
        finally:
            shutil.rmtree(input_files_directory)

    # TODO: Move it to test_env (to CliInputsTests)
    def test_local_init_with_wildcard_inputs(self):
        input_files_directory = self._generate_multiple_input_files()
        try:
            self._local_init(
                inputs=[os.path.join(input_files_directory, 'f*.yaml')])
            self._assert_multiple_outputs()
        finally:
            shutil.rmtree(input_files_directory)

    # TODO: is this still relevant
    def test_local_provider_context(self):
        self._init()
        with open(utils.get_configuration_path()) as f:
            config = yaml.safe_load(f.read())
        with open(utils.get_configuration_path(), 'w') as f:
            config['local_provider_context'] = {
                'stub1': 'value1'
            }
            f.write(yaml.safe_dump(config))
        self._local_init()
        self._local_execute()
        output = self.invoke('cfy local outputs')
        self.assertIn('"provider_context":', output)
        self.assertIn('stub1', output)
        self.assertIn('value1', output)

    # TODO: Should be tested generally - pretty much for each command
    def test_execute_with_no_init(self):
        self._assert_ex('cfy local execute -w run_test_op_on_nodes',
                        'has not been initialized',
                        possible_solutions=[
                            "Run `cfy local init` in this directory"
                        ])

    def test_outputs_with_no_init(self):
        self._assert_ex('cfy local outputs',
                        'has not been initialized',
                        possible_solutions=[
                            "Run `cfy local init` in this directory"
                        ])

    def test_instances_with_no_init(self):
        self._assert_ex('cfy local instances',
                        'has not been initialized',
                        possible_solutions=[
                            "Run `cfy local init` in this directory"
                        ])

    # TODO: Is this still relevant?
    def test_install_agent(self):
        blueprint_path = '{0}/local/install-agent-blueprint.yaml' \
            .format(BLUEPRINTS_DIR)
        try:
            self.invoke('cfy local init -p {0}'.format(blueprint_path))
            self.fail('ValueError was expected')
        except ValueError as e:
            self.assertIn("'install_agent': true is not supported "
                          "(it is True by default) "
                          "when executing local workflows. "
                          "The 'install_agent' property must be set to false "
                          "for each node of type {0}.".format(HOST_TYPE),
                          e.message)

    # TODO: Is this still relevant?
    def test_install_plugins_missing_windows_agent_installer(self):
        blueprint_path = '{0}/local/windows_installers_blueprint.yaml'\
            .format(BLUEPRINTS_DIR)
        self.invoke('cfy local init -p {0}'.format(blueprint_path))

    # TODO: Move it to test_env (to TestLogger?)
    def test_verbose_logging(self):
        def run(level=None, message=None, error=None, user_cause=None,
                verbose_flag=''):
            params = {}
            if level is not None:
                params['level'] = level
            if message is not None:
                params['message'] = message
            if error is not None:
                params['error'] = error
            if user_cause is not None:
                params['user_cause'] = user_cause
            params_path = os.path.join(utils.get_cwd(), 'parameters.json')
            with open(params_path, 'w') as f:
                f.write(json.dumps(params))
            with cloudify_cli.tests.commands.mocks.mock_stdout() as output:
                self.invoke('cfy local execute -w logging_workflow '
                                   '-p {0} {1}'.format(params_path,
                                                       verbose_flag))
            return output.getvalue()

        blueprint_path = '{0}/logging/blueprint.yaml'.format(BLUEPRINTS_DIR)
        self.invoke('cfy local init -p {0}'.format(blueprint_path))

        message = 'MESSAGE'

        def assert_output(verbosity,
                          expect_debug=False,
                          expect_traceback=False):
            output = run(level='INFO', message=message, verbose_flag=verbosity)
            self.assertIn('INFO: {0}'.format(message), output)
            output = run(level='DEBUG', message=message,
                         verbose_flag=verbosity)
            if expect_debug:
                self.assertIn('DEBUG: {0}'.format(message), output)
            else:
                self.assertNotIn(message, output)
            output = run(message=message, error=True, verbose_flag=verbosity)
            self.assertIn('Task failed', output)
            self.assertIn(message, output)
            if expect_traceback:
                self.assertIn('Traceback', output)
                self.assertNotIn('Causes', output)
            else:
                self.assertNotIn('Traceback', output)
            output = run(message=message, error=True, user_cause=True,
                         verbose_flag=verbosity)
            self.assertIn('Task failed', output)
            self.assertIn(message, output)
            if expect_traceback:
                if expect_traceback:
                    self.assertIn('Traceback', output)
                    self.assertIn('Causes', output)
                else:
                    self.assertNotIn('Traceback', output)
        assert_output(verbosity='')
        assert_output(verbosity='-v', expect_traceback=True)
        assert_output(verbosity='-vv', expect_traceback=True,
                      expect_debug=True)
        assert_output(verbosity='-vvv', expect_traceback=True,
                      expect_debug=True)
