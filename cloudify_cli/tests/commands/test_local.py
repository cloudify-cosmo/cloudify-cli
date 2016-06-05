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

import logging
import sys
import os
import json
import tempfile
import shutil

import yaml
import nose
from mock import patch

from dsl_parser import exceptions as parser_exceptions

import cloudify.utils
import cloudify.exceptions
import cloudify.logs
from cloudify.decorators import operation, workflow
from cloudify import ctx as op_ctx
from cloudify.exceptions import CommandExecutionException
from cloudify.workflows import ctx as workflow_ctx
from cloudify.workflows import tasks as workflow_tasks
from dsl_parser.constants import HOST_TYPE

from cloudify_cli import utils
from cloudify_cli import common
from cloudify_cli.commands import local
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_cli.tests.commands.test_cli_command import \
    (BLUEPRINTS_DIR,
     TEST_WORK_DIR)
from cloudify_cli.constants import DEFAULT_BLUEPRINT_PATH
from cloudify_cli.constants import DEFAULT_PARAMETERS
from cloudify_cli.constants import DEFAULT_TASK_THREAD_POOL_SIZE
from cloudify_cli.constants import DEFAULT_INSTALL_WORKFLOW
from cloudify_cli.constants import DEFAULT_UNINSTALL_WORKFLOW
from cloudify_cli.tests.commands import utils as test_utils


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

    def _assert_multiple_outputs(self):
        output = cli_runner.run_cli('cfy local outputs')
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

    def test_local_init_with_inputs(self):
        fd, inputs_file = tempfile.mkstemp()
        os.close(fd)
        with open(inputs_file, 'w') as f:
            f.write('input3: new_input3')
        try:
            self._local_init(
                inputs=['input1=new_input1;input2=new_input2', inputs_file])
            self._assert_multiple_outputs()
        finally:
            os.remove(inputs_file)

    def test_local_init_with_directory_inputs(self):
        input_files_directory = self._generate_multiple_input_files()
        try:
            self._local_init(inputs=[input_files_directory])
            self._assert_multiple_outputs()
        finally:
            shutil.rmtree(input_files_directory)

    def test_local_init_with_wildcard_inputs(self):
        input_files_directory = self._generate_multiple_input_files()
        try:
            self._local_init(
                inputs=[os.path.join(input_files_directory, 'f*.yaml')])
            self._assert_multiple_outputs()
        finally:
            shutil.rmtree(input_files_directory)

    def test_local_execute(self):
        self._local_init()
        self._local_execute()
        output = cli_runner.run_cli('cfy local outputs')
        self.assertIn('"param": "default_param"', output)

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
        output = cli_runner.run_cli('cfy local outputs')
        self.assertIn('"provider_context":', output)
        self.assertIn('stub1', output)
        self.assertIn('value1', output)

    def test_validate_definitions_version(self):
        blueprint = 'blueprint_validate_definitions_version'
        self._init()
        self.assertRaises(
            parser_exceptions.DSLParsingLogicException,
            self._local_init, blueprint=blueprint)
        with open(utils.get_configuration_path()) as f:
            config = yaml.safe_load(f.read())
        with open(utils.get_configuration_path(), 'w') as f:
            config['validate_definitions_version'] = False
            f.write(yaml.safe_dump(config))
        # Parsing occurs during init
        self._local_init(blueprint=blueprint)

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

    def test_empty_requirements(self):
        blueprint = 'blueprint_without_plugins'
        blueprint_path = '{0}/local/{1}.yaml'.format(BLUEPRINTS_DIR,
                                                     blueprint)
        cli_runner.run_cli('cfy local init --install-plugins -p {0}'
                           .format(blueprint_path))

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

        expected_requirements = {
            'http://localhost/plugin.zip',
            os.path.join(
                os.path.dirname(local.__file__),
                'plugins',
                'local_plugin'),
            'http://localhost/host_plugin.zip'}
        requirements_file_path = os.path.join(TEST_WORK_DIR,
                                              'requirements.txt')

        cli_runner.run_cli('cfy local create-requirements -p '
                           '{0}/local/blueprint_with_plugins.yaml -o {1}'
                           .format(BLUEPRINTS_DIR, requirements_file_path))

        with open(requirements_file_path, 'r') as f:
            actual_requirements = set(f.read().split())
            self.assertEqual(actual_requirements, expected_requirements)

    def test_create_requirements_existing_output_file(self):
        blueprint_path = '{0}/local/blueprint_with_plugins.yaml'\
            .format(BLUEPRINTS_DIR)
        file_path = tempfile.mktemp()
        with open(file_path, 'w') as f:
            f.write('')
        self._assert_ex(
            cli_cmd='cfy local create-requirements -p {0} -o {1}'
                    .format(blueprint_path, file_path),
            err_str_segment='output path already exists : '
                            '{0}'.format(file_path)
        )

    def test_create_requirements_no_output(self):

        from cloudify_cli.tests.resources.blueprints import local

        expected_requirements = {
            'http://localhost/plugin.zip',
            os.path.join(
                os.path.dirname(local.__file__),
                'plugins',
                'local_plugin'),
            'http://localhost/host_plugin.zip'}
        output = cli_runner.run_cli(
            'cfy local create-requirements -p '
            '{0}/local/blueprint_with_plugins.yaml'
            .format(BLUEPRINTS_DIR))
        for requirement in expected_requirements:
            self.assertIn(requirement, output)

    def test_install_agent(self):
        blueprint_path = '{0}/local/install-agent-blueprint.yaml' \
            .format(BLUEPRINTS_DIR)
        try:
            cli_runner.run_cli('cfy local init -p {0}'.format(blueprint_path))
            self.fail('ValueError was expected')
        except ValueError as e:
            self.assertIn("'install_agent': true is not supported "
                          "(it is True by default) "
                          "when executing local workflows. "
                          "The 'install_agent' property must be set to false "
                          "for each node of type {0}.".format(HOST_TYPE),
                          e.message)

    def test_install_plugins(self):

        blueprint_path = '{0}/local/blueprint_with_plugins.yaml'\
            .format(BLUEPRINTS_DIR)
        try:
            cli_runner.run_cli('cfy local install-plugins -p {0}'
                               .format(blueprint_path))
        except CommandExecutionException as e:
            # Expected pip install to start
            self.assertIn('pip install -r /tmp/requirements_',
                          e.message)

    def test_install_plugins_missing_windows_agent_installer(self):
        blueprint_path = '{0}/local/windows_installers_blueprint.yaml'\
            .format(BLUEPRINTS_DIR)
        cli_runner.run_cli('cfy local init -p {0}'.format(blueprint_path))

    @patch('cloudify_cli.commands.local.execute')
    @patch('cloudify_cli.commands.local.init')
    def test_install_command_default_init_arguments(self, local_init_mock, *_):

        local_install_command = 'cfy local install'
        cli_runner.run_cli(local_install_command)

        local_init_mock.assert_called_with(
            blueprint_path=DEFAULT_BLUEPRINT_PATH,
            inputs=None,
            install_plugins=False
        )

    @patch('cloudify_cli.commands.local.execute')
    @patch('cloudify_cli.commands.local.init')
    def test_install_command_custom_init_arguments(self, local_init_mock, *_):

        local_install_command = \
            'cfy local install -p blueprint_path.yaml -i key=value ' \
            '--install-plugins'

        cli_runner.run_cli(local_install_command)

        local_init_mock.assert_called_with(
            blueprint_path='blueprint_path.yaml',
            inputs=["key=value"],
            install_plugins=True
        )

    @patch('cloudify_cli.commands.local.init')
    @patch('cloudify_cli.commands.local.execute')
    def test_install_command_default_execute_arguments(self,
                                                       local_execute_mock,
                                                       *_):
        local_install_command = 'cfy local install'
        cli_runner.run_cli(local_install_command)

        local_execute_mock.assert_called_with(
            workflow_id=DEFAULT_INSTALL_WORKFLOW,
            parameters=DEFAULT_PARAMETERS,
            allow_custom_parameters=False,
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=DEFAULT_TASK_THREAD_POOL_SIZE
        )

    @patch('cloudify_cli.commands.local.init')
    @patch('cloudify_cli.commands.local.execute')
    def test_install_command_custom_execute_arguments(self,
                                                      local_execute_mock,
                                                      *_):

        local_install_command = 'cfy local install ' \
                                '-w my-install ' \
                                '--parameters key=value ' \
                                '--allow-custom-parameters ' \
                                '--task-retries 14 ' \
                                '--task-retry-interval 7 ' \
                                '--task-thread-pool-size 87'
        cli_runner.run_cli(local_install_command)

        local_execute_mock.assert_called_with(workflow_id='my-install',
                                              parameters=["key=value"],
                                              allow_custom_parameters=True,
                                              task_retries=14,
                                              task_retry_interval=7,
                                              task_thread_pool_size=87
                                              )

    @patch('cloudify_cli.commands.local.execute')
    def test_uninstall_command_execute_default_arguments(self,
                                                         local_execute_mock
                                                         ):
        local_uninstall_command = 'cfy local uninstall'

        cli_runner.run_cli(local_uninstall_command)

        local_execute_mock.assert_called_with(
            workflow_id=DEFAULT_UNINSTALL_WORKFLOW,
            parameters=DEFAULT_PARAMETERS,
            allow_custom_parameters=False,
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=DEFAULT_TASK_THREAD_POOL_SIZE)

    @patch('cloudify_cli.commands.local.execute')
    def test_uninstall_command_execute_custom_arguments(self,
                                                        local_execute_mock
                                                        ):
        local_uninstall_command = 'cfy local uninstall ' \
                                  '-w my-uninstall ' \
                                  '--parameters key=value ' \
                                  '--allow-custom-parameters ' \
                                  '--task-retries 14 ' \
                                  '--task-retry-interval 7 ' \
                                  '--task-thread-pool-size 87'

        cli_runner.run_cli(local_uninstall_command)

        local_execute_mock.assert_called_with(
            workflow_id='my-uninstall',
            parameters=['key=value'],
            allow_custom_parameters=True,
            task_retries=14,
            task_retry_interval=7,
            task_thread_pool_size=87)

    def test_uninstall_command_removes_local_storage_dir(self):

        sample_blueprint_path = os.path.join(BLUEPRINTS_DIR,
                                             'local',
                                             'blueprint.yaml')

        # a custom workflow is used because the sample blueprint path does not
        # have an 'install' workflow
        cli_runner.run_cli('cfy local install '
                           '-w run_test_op_on_nodes '
                           '-p {0}'
                           .format(sample_blueprint_path)
                           )
        self.assertTrue(os.path.isdir(local._storage_dir()))

        # a custom workflow is used because the sample blueprint path does not
        # have an 'uninstall' workflow
        cli_runner.run_cli('cfy local uninstall '
                           '-w run_test_op_on_nodes '
                           .format(sample_blueprint_path)
                           )

        self.assertFalse(os.path.isdir(local._storage_dir()))

    @nose.tools.nottest
    def test_local_outputs(self):
        # tested extensively by the other tests
        self.fail()

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
            with test_utils.mock_stdout() as output:
                cli_runner.run_cli('cfy local execute -w logging_workflow '
                                   '-p {0} {1}'.format(params_path,
                                                       verbose_flag))
            return output.getvalue()

        blueprint_path = '{0}/logging/blueprint.yaml'.format(BLUEPRINTS_DIR)
        cli_runner.run_cli('cfy local init -p {0}'.format(blueprint_path))

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

    def _init(self):
        cli_runner.run_cli('cfy init')

    def _local_init(self,
                    inputs=None,
                    blueprint='blueprint',
                    install_plugins=False):

        blueprint_path = '{0}/local/{1}.yaml'.format(BLUEPRINTS_DIR,
                                                     blueprint)
        flags = '--install-plugins' if install_plugins else ''
        command = 'cfy local init {0} -p {1}'.format(flags,
                                                     blueprint_path)
        inputs = inputs or []
        for inputs_instance in inputs:
            command += ' -i {0}'.format(inputs_instance)
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
    props = op_ctx.instance.runtime_properties
    props['param'] = param
    props['custom_param'] = custom_param
    props['provider_context'] = op_ctx.provider_context


@workflow
def mock_workflow(param, custom_param=None, **kwargs):
    for node in workflow_ctx.nodes:
        for instance in node.instances:
            instance.execute_operation('test.op', kwargs={
                'param': param,
                'custom_param': custom_param
            })


@workflow
def logging_workflow(**kwargs):
    kwargs.pop('ctx', None)
    graph = workflow_ctx.graph_mode()
    instance = next(workflow_ctx.node_instances)
    task = instance.execute_operation('test.op', kwargs=kwargs)

    def on_failure(tsk):
        return workflow_tasks.HandlerResult.ignore()
    task.on_failure = on_failure
    graph.add_task(task)
    graph.execute()


@operation
def logging_operation(level, message, error=False, user_cause=False, **kwargs):
    if error:
        causes = []
        if user_cause:
            try:
                raise RuntimeError(message)
            except RuntimeError:
                _, ex, tb = sys.exc_info()
                causes.append(cloudify.utils.exception_to_error_cause(
                    ex, tb))
        raise cloudify.exceptions.NonRecoverableError(message, causes=causes)
    else:
        level = getattr(logging, level)
        op_ctx.logger.log(level, message)
