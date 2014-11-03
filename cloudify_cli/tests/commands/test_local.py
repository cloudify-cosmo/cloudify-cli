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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

"""
Tests all commands that start with 'cfy blueprints'
"""

import os
import json
import nose
from sets import Set


from cloudify.decorators import operation, workflow
from cloudify import ctx as op_ctx
from cloudify.exceptions import CommandExecutionException
from cloudify.workflows import ctx as workflow_ctx

from cloudify_cli import common
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_cli.tests.commands.test_cli_command import \
    (BLUEPRINTS_DIR,
     TEST_WORK_DIR)


class LocalTest(CliCommandTest):

    def setUp(self):
        super(LocalTest, self).setUp()

    def test_local_init_missing_blueprint_path(self):
        cli_runner.run_cli_expect_system_exit_code(
            'cfy local init', 2)

    def test_local_init_invalid_blueprint_path(self):
        self._assert_ex(
            'cfy local init -p idonotexist.yaml',
            'No such file or directory')

    def test_local_init(self):
        self._local_init()
        output = cli_runner.run_cli('cfy local outputs')
        self.assertIn('"param": null', output)
        self.assertIn('"custom_param": null', output)
        self.assertIn('"input1": "default_input1"', output)

    def test_local_init_with_inputs(self):
        self._local_init(inputs={'input1': 'new_input1'})
        output = cli_runner.run_cli('cfy local outputs')
        self.assertIn('"input1": "new_input1"', output)

    def test_local_execute(self):
        self._local_init()
        self._local_execute()
        output = cli_runner.run_cli('cfy local outputs')
        self.assertIn('"param": "default_param"', output)

    def test_local_init_install_plugins(self):

        blueprint_path = '{0}/local/{1}.yaml' \
            .format(BLUEPRINTS_DIR,
                    'blueprint_with_plugins')

        self.assert_method_called(
            cli_command='cfy local init --install-plugins -p {0}'
                        .format(blueprint_path),
            module=common,
            function_name='install_blueprint_plugins',
            kwargs={'blueprint_path': blueprint_path}
        )

    def test_local_init_missing_plugin(self):

        blueprint = 'blueprint_with_plugins'
        blueprint_path = '{0}/local/{1}.yaml'.format(BLUEPRINTS_DIR,
                                                     blueprint)

        expected_possible_solutions = [
            "Run 'cfy local init --install-plugins -p {0}'"
            .format(blueprint_path),
            "Run 'cfy local install-plugins -p {0}'"
            .format(blueprint_path)
        ]
        try:
            self._local_init(blueprint=blueprint)
            self.fail('Excepted ImportError')
        except ImportError as e:
            actual_possible_solutions = e.possible_solutions
            self.assertEqual(actual_possible_solutions,
                             expected_possible_solutions)

    def test_local_execute_with_params(self):
        self._local_init()
        self._local_execute(parameters={'param': 'new_param'})
        output = cli_runner.run_cli('cfy local outputs')
        self.assertIn('"param": "new_param"', output)

    def test_local_execute_with_params_allow_custom_false(self):
        self._local_init()
        self._local_execute(parameters={'custom_param': 'custom_param_value'},
                            allow_custom=False)

    def test_local_execute_with_params_allow_custom_true(self):
        self._local_init()
        self._local_execute(parameters={'custom_param': 'custom_param_value'},
                            allow_custom=True)
        output = cli_runner.run_cli('cfy local outputs')
        self.assertIn('"custom_param": "custom_param_value"', output)

    def test_local_instances(self):
        self._local_init()
        self._local_execute()
        output = cli_runner.run_cli('cfy local instances')
        self.assertIn('"node_id": "node"', output)

    def test_local_instances_with_existing_node_id(self):
        self._local_init()
        self._local_execute()
        output = cli_runner.run_cli('cfy local instances --node-id node')
        self.assertIn('"node_id": "node"', output)

    def test_local_instances_with_non_existing_node_id(self):
        self._local_init()
        self._local_execute()
        self._assert_ex('cfy local instances --node-id no_node',
                        'No node with id: no_node')

    def test_execute_with_no_init(self):
        self._assert_ex('cfy local execute -w run_test_op_on_nodes',
                        'has not been initialized',
                        possible_solutions=[
                            "Run 'cfy local init' in this directory"
                        ])

    def test_outputs_with_no_init(self):
        self._assert_ex('cfy local outputs',
                        'has not been initialized',
                        possible_solutions=[
                            "Run 'cfy local init' in this directory"
                        ])

    def test_instances_with_no_init(self):
        self._assert_ex('cfy local instances',
                        'has not been initialized',
                        possible_solutions=[
                            "Run 'cfy local init' in this directory"
                        ])

    def test_create_requirements(self):

        from cloudify_cli.tests.resources.blueprints import local

        expected_requirements = Set([
            'http://localhost/plugin.zip',
            os.path.join(os.path.dirname(local.__file__),
                         'plugins',
                         'local_plugin'),
            'http://localhost/host_plugin.zip'
        ])
        requirements_file_path = os.path.join(TEST_WORK_DIR,
                                              'requirements.txt')

        cli_runner.run_cli('cfy local create-requirements -p '
                           '{0}/local/blueprint_with_plugins.yaml -o {1}'
                           .format(BLUEPRINTS_DIR, requirements_file_path))

        with open(requirements_file_path, 'r') as f:
            actual_requirements = Set(f.read().split())
            self.assertEqual(actual_requirements, expected_requirements)

    def test_create_requirements_no_output(self):
        self.fail("TODO")

    def test_install_plugins(self):
        try:
            cli_runner.run_cli('cfy local install-plugins -p '
                               '{0}/local/blueprint_with_plugins.yaml'
                               .format(BLUEPRINTS_DIR))
        except CommandExecutionException as e:
            # Expected pip install to start
            # TODO - assert pip installs the correct
            # TODO - sources
            self.assertIn('pip install',
                          e.message)

    @nose.tools.nottest
    def test_local_outputs(self):
        # tested extensively by the other tests
        self.fail()

    def _local_init(self,
                    inputs=None,
                    blueprint='blueprint',
                    install_plugins=False):

        blueprint_path = '{0}/local/{1}.yaml'.format(BLUEPRINTS_DIR,
                                                     blueprint)
        flags = '--install-plugins' if install_plugins else ''
        command = 'cfy local init {0} -p {1}'.format(flags,
                                                     blueprint_path)
        if inputs:
            inputs_path = os.path.join(TEST_WORK_DIR,
                                       'temp_inputs.json')
            with open(inputs_path, 'w') as f:
                f.write(json.dumps(inputs))
            command = '{0} -i {1}'.format(command, inputs_path)
        cli_runner.run_cli(command)

    def _local_execute(self, parameters=None,
                       allow_custom=None,
                       workflow_name='run_test_op_on_nodes'):
        if parameters:
            parameters_path = os.path.join(TEST_WORK_DIR,
                                           'temp_parameters.json')
            with open(parameters_path, 'w') as f:
                f.write(json.dumps(parameters))
            command = 'cfy local execute -w {0} -p {1}'\
                      .format(workflow_name,
                              parameters_path)
            if allow_custom is True:
                cli_runner.run_cli('{0} --allow-custom-parameters'
                                   .format(command))
            elif allow_custom is False:
                self._assert_ex(command, 'does not have the following')
            else:
                cli_runner.run_cli(command)
        else:
            cli_runner.run_cli('cfy local execute -w {0}'
                               .format(workflow_name))


@operation
def mock_op(param, custom_param=None, **kwargs):
    op_ctx.instance.runtime_properties['param'] = param
    op_ctx.instance.runtime_properties['custom_param'] = custom_param


@workflow
def mock_workflow(param, custom_param=None, **kwargs):
    for node in workflow_ctx.nodes:
        for instance in node.instances:
            instance.execute_operation('test.op', kwargs={
                'param': param,
                'custom_param': custom_param
            })
