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

from cloudify.decorators import operation, workflow
from cloudify import ctx as op_ctx
from cloudify.workflows import ctx as workflow_ctx

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
                        'has not been initialized')

    def test_outputs_with_no_init(self):
        self._assert_ex('cfy local outputs',
                        'has not been initialized')

    def test_instances_with_no_init(self):
        self._assert_ex('cfy local instances',
                        'has not been initialized')

    @nose.tools.nottest
    def test_local_outputs(self):
        # tested extensively by the other tests
        self.fail()

    def _local_init(self, inputs=None):
        if inputs:
            inputs_path = os.path.join(TEST_WORK_DIR, 'temp_inputs.json')
            with open(inputs_path, 'w') as f:
                f.write(json.dumps(inputs))
            cli_runner.run_cli('cfy local init -p {0}/local/blueprint.yaml '
                               '-i {1}'
                               .format(BLUEPRINTS_DIR, inputs_path))
        else:
            cli_runner.run_cli('cfy local init -p {0}/local/blueprint.yaml'
                               .format(BLUEPRINTS_DIR))

    def _local_execute(self, parameters=None, allow_custom=None):
        if parameters:
            parameters_path = os.path.join(TEST_WORK_DIR,
                                           'temp_parameters.json')
            with open(parameters_path, 'w') as f:
                f.write(json.dumps(parameters))
            command = 'cfy local execute -w run_test_op_on_nodes -p {0}'\
                      .format(parameters_path)
            if allow_custom is True:
                cli_runner.run_cli('{0} --allow-custom-parameters'
                                   .format(command))
            elif allow_custom is False:
                self._assert_ex(command, 'does not have the following')
            else:
                cli_runner.run_cli(command)
        else:
            cli_runner.run_cli('cfy local execute -w run_test_op_on_nodes')


@operation
def mock_op(param, custom_param=None, **kwargs):
    op_ctx.runtime_properties['param'] = param
    op_ctx.runtime_properties['custom_param'] = custom_param


@workflow
def mock_workflow(param, custom_param=None, **kwargs):
    for node in workflow_ctx.nodes:
        for instance in node.instances:
            instance.execute_operation('test.op', kwargs={
                'param': param,
                'custom_param': custom_param
            })
