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

import json

import mock

from cloudify_cli import common
from cloudify_cli.bootstrap import bootstrap
from cloudify_cli.tests.commands.test_cli_command import \
    CliCommandTest, BLUEPRINTS_DIR


class BootstrapTest(CliCommandTest):

    def test_bootstrap_install_plugins(self):
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = 'cfy bootstrap --install-plugins {0}'.format(blueprint_path)

        with mock.patch('cloudify_cli.bootstrap.bootstrap.'
                        'validate_manager_deployment_size'):
            self.assert_method_called(
                command=command,
                module=common,
                function_name='install_blueprint_plugins',
                kwargs=dict(blueprint_path=blueprint_path))

    def test_bootstrap_no_validations_install_plugins(self):
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = ('cfy bootstrap --skip-validations '
                   '--install-plugins {0}'.format(blueprint_path))

        self.assert_method_called(
            command=command,
            module=common,
            function_name='install_blueprint_plugins',
            kwargs=dict(blueprint_path=blueprint_path)
        )

    def test_bootstrap_no_validations_add_ignore_bootstrap_validations(self):

        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        command = ('cfy bootstrap --skip-validations {0} '
                   '-i "some_input=some_value"'.format(blueprint_path))

        self.assert_method_called(
            command=command,
            module=common,
            function_name='add_ignore_bootstrap_validations_input',
            args=[[u'some_input=some_value']]
        )

    def test_viable_ignore_bootstrap_validations_input(self):
        inputs = []
        inputs = common.add_ignore_bootstrap_validations_input(inputs)
        ignore_input = json.loads(inputs[0])
        self.assertTrue(ignore_input['ignore_bootstrap_validations'])

    def test_bootstrap_missing_plugin(self):

        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = 'cfy bootstrap {0}'.format(blueprint_path)

        with mock.patch('cloudify_cli.bootstrap.bootstrap.'
                        'validate_manager_deployment_size'):
            self.invoke(
                command=command,
                err_str_segment='No module named tasks',
                exception=ImportError
                # TODO: put back
                # possible_solutions=[
                #     "Run 'cfy local install-plugins {0}'".format(
                #         blueprint_path),
                #     "Run 'cfy bootstrap --install-plugins {0}'".format(
                #         blueprint_path)]
            )

    def test_bootstrap_no_validation_missing_plugin(self):

        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = 'cfy bootstrap --skip-validations {0}'.format(
            blueprint_path)

        self.invoke(
            command=command,
            err_str_segment='No module named tasks',
            exception=ImportError
            # TODO: put back
            # possible_solutions=[
            #     "Run 'cfy local install-plugins -p {0}'"
            #     .format(blueprint_path),
            #     "Run 'cfy bootstrap --install-plugins -p {0}'"
            #     .format(blueprint_path)
            # ]
        )

    def test_bootstrap_validate_manager_deployment_size(self):
        # verifying validation over manager deployment size is called before
        # calling bootstrap
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        command = 'cfy bootstrap --validate-only {0}'.format(blueprint_path)

        self.assert_method_called(
            command=command,
            module=bootstrap,
            function_name='validate_manager_deployment_size',
            kwargs=dict(blueprint_path=blueprint_path))

    def test_bootstrap_skip_validate_manager_deployment_size(self):
        # verifying validation over manager deployment size is not called
        # when the "--skip-validation" flag is used
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        command = ('cfy bootstrap --validate-only --skip-validations '
                   '{0}'.format(blueprint_path))

        self.assert_method_not_called(
            command=command,
            module=bootstrap,
            function_name='validate_manager_deployment_size')
