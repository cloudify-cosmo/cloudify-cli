########
# Copyright (c) 2021 Cloudify.co Ltd. All rights reserved
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
from datetime import date
from mock import patch, Mock

from .test_base import CliCommandTest
from .constants import (TEST_LABELS,
                        BLUEPRINTS_DIR,
                        SAMPLE_BLUEPRINT_PATH,
                        SAMPLE_ARCHIVE_PATH,
                        STUB_BLUEPRINT_ID,
                        SAMPLE_INPUTS_PATH,
                        STUB_DEPLOYMENT_ID,
                        STUB_DIRECTORY_NAME,
                        DEFAULT_BLUEPRINT_FILE_NAME)


class ApplyTest(CliCommandTest):
    def setUp(self):
        super(ApplyTest, self).setUp()
        self.use_manager()

    def _mock_client_deployment_id(self, deployment_id):
        deployment_mock = Mock()
        deployment_mock.id = deployment_id
        self.client.deployments.get = Mock(return_value=deployment_mock)

    @patch('cloudify_cli.commands.install.manager')
    def test_apply_no_deployment_id_argument(self, install_mock):
        self.client.deployments.get = Mock(return_value=None)
        self.invoke('cfy apply --blueprint-path {path} '.format(
            path=SAMPLE_BLUEPRINT_PATH))
        install_mock.assert_called()
        install_args = install_mock.call_args_list[0][1]

        self.assertEqual(
            install_args['blueprint_path'],
            SAMPLE_BLUEPRINT_PATH
        )
        # Infer deployment id and blueprint id from blueprint path.
        self.assertEqual(
            install_args['blueprint_id'],
            STUB_DIRECTORY_NAME
        )

        self.assertEqual(
            install_args['deployment_id'],
            STUB_DIRECTORY_NAME
        )

    @patch('cloudify_cli.commands.apply.os.getcwd',
           return_value=os.path.join(BLUEPRINTS_DIR, STUB_DIRECTORY_NAME))
    @patch('cloudify_cli.commands.install.manager')
    def test_apply_default_values(self, install_mock, *_):
        self.client.deployments.get = Mock(return_value=None)
        self.invoke('cfy apply')
        install_mock.assert_called()
        install_args = install_mock.call_args_list[0][1]

        self.assertEqual(
            install_args['blueprint_path'],
            SAMPLE_BLUEPRINT_PATH
        )
        # Infer deployment id and blueprint id from default blueprint path.
        self.assertEqual(
            install_args['blueprint_id'],
            STUB_DIRECTORY_NAME
        )

        self.assertEqual(
            install_args['deployment_id'],
            STUB_DIRECTORY_NAME
        )

    @patch('cloudify_cli.commands.install.manager')
    def test_apply_call_to_install_with_blueprint_id(self, install_mock):
        self.client.deployments.get = Mock(return_value=None)
        apply_command = 'cfy apply --blueprint-path {bl_path}' \
                        ' --deployment-id {dep_id} -b {bl_id}' \
                        ' --inputs={inputs} '.format(
                                                bl_path=SAMPLE_BLUEPRINT_PATH,
                                                dep_id=STUB_DEPLOYMENT_ID,
                                                bl_id=STUB_BLUEPRINT_ID,
                                                inputs=SAMPLE_INPUTS_PATH)
        self.invoke(apply_command)
        install_mock.assert_called()
        install_args = install_mock.call_args_list[0][1]

        self.assertEqual(
            install_args['blueprint_path'],
            SAMPLE_BLUEPRINT_PATH
        )

        self.assertEqual(
            install_args['blueprint_id'],
            STUB_BLUEPRINT_ID
        )

        self.assertEqual(
            install_args['deployment_id'],
            STUB_DEPLOYMENT_ID
        )
        self.assertEqual(
            install_args['inputs'],
            {'key1': 'val1', 'key2': 'val2'}
        )

    @patch('cloudify_cli.commands.deployments.manager_update')
    @patch('cloudify_cli.commands.apply.datetime')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_upload_blueprint_before_update(self,
                                            blueprint_upload_mock,
                                            datetime_mock,
                                            *_):
        self._mock_client_deployment_id(deployment_id=STUB_DEPLOYMENT_ID)
        datetime_mock.now.return_value = date(2021, 1, 1)
        apply_command = 'cfy apply --blueprint-path {bl_path} ' \
                        '--deployment-id {dep_id} --validate ' \
                        '--blueprint-labels {labels}'.format(
                                                bl_path=SAMPLE_BLUEPRINT_PATH,
                                                dep_id=STUB_DEPLOYMENT_ID,
                                                labels=TEST_LABELS)
        self.invoke(apply_command)
        blueprint_upload_mock.assert_called_with(
            blueprint_path=SAMPLE_BLUEPRINT_PATH,
            blueprint_id=STUB_DEPLOYMENT_ID + '-01-01-2021-00-00-00',
            validate=True,
            visibility='tenant',
            tenant_name=None,
            labels=[{'label_key': 'label_value'}])

    @patch('cloudify_cli.commands.deployments.manager_update')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_upload_blueprint_before_update_with_blueprint_id(
            self,
            blueprint_upload_mock,
            *_):
        self._mock_client_deployment_id(deployment_id=STUB_DEPLOYMENT_ID)
        apply_command = 'cfy apply --blueprint-path {bl_path} ' \
                        '--deployment-id {dep_id} -b {bl_id} ' \
                        '--blueprint-labels {labels} ' \
                        '--validate'.format(bl_path=SAMPLE_BLUEPRINT_PATH,
                                            dep_id=STUB_DEPLOYMENT_ID,
                                            bl_id=STUB_BLUEPRINT_ID,
                                            labels=TEST_LABELS)
        self.invoke(apply_command)
        blueprint_upload_mock.assert_called_with(
            blueprint_path=SAMPLE_BLUEPRINT_PATH,
            blueprint_id=STUB_BLUEPRINT_ID,
            validate=True,
            visibility='tenant',
            tenant_name=None,
            labels=[{'label_key': 'label_value'}])

    @patch('cloudify_cli.commands.deployments.manager_update')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_upload_blueprint_before_update_with_zip(
            self,
            blueprint_upload_mock,
            *_):
        self._mock_client_deployment_id(deployment_id=STUB_DEPLOYMENT_ID)
        apply_command = 'cfy apply --blueprint-path {bl_path} ' \
                        '--deployment-id {dep_id} -n {bl_file_name} ' \
                        '-b {bl_id}'.format(
                            bl_path=SAMPLE_ARCHIVE_PATH,
                            dep_id=STUB_DEPLOYMENT_ID,
                            bl_file_name=DEFAULT_BLUEPRINT_FILE_NAME,
                            bl_id=STUB_BLUEPRINT_ID)
        self.invoke(apply_command)
        install_args = blueprint_upload_mock.call_args_list[0][1]

        self.assertEqual(
            install_args['blueprint_path'].startswith('/tmp'),
            True
        )
        self.assertEqual(
            install_args['blueprint_id'],
            STUB_BLUEPRINT_ID
        )

    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.deployments.add_deployment_labels')
    @patch('cloudify_cli.commands.deployments.manager_update')
    def test_apply_call_deployment_update(self,
                                          deployment_update_mock,
                                          add_deployment_labels_mock,
                                          *_):
        self._mock_client_deployment_id(deployment_id=STUB_DEPLOYMENT_ID)
        apply_command = 'cfy apply --blueprint-path {bl_path} ' \
                        '--deployment-id {dep_id} -b {bl_id} ' \
                        '--inputs={inputs} --deployment-labels {labels}'\
            .format(bl_path=SAMPLE_BLUEPRINT_PATH,
                    dep_id=STUB_DEPLOYMENT_ID,
                    bl_id=STUB_BLUEPRINT_ID,
                    inputs=SAMPLE_INPUTS_PATH,
                    labels=TEST_LABELS)

        self.invoke(apply_command)

        deployment_update_mock.assert_called_with(
            deployment_id=STUB_DEPLOYMENT_ID,
            blueprint_path=None,
            inputs={'key1': 'val1', 'key2': 'val2'},
            reinstall_list=(),
            skip_install=False,
            skip_uninstall=False,
            skip_reinstall=True,
            ignore_failure=False,
            install_first=False,
            preview=False,
            dont_update_plugins=False,
            workflow_id=None,
            force=False,
            include_logs=True,
            json_output=False,
            tenant_name=None,
            blueprint_id=STUB_BLUEPRINT_ID,
            visibility='tenant',
            validate=False,
            runtime_only_evaluation=False,
            auto_correct_types=False,
            reevaluate_active_statuses=False)
        add_deployment_labels_mock.assert_called_with(
            labels_list=[{'label_key': 'label_value'}],
            deployment_id=STUB_DEPLOYMENT_ID,
            tenant_name=None)

    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.deployments.manager_update')
    def test_apply_call_to_update_with_dont_skip_reinstall(
            self,
            deployment_update_mock,
            *_):
        self._mock_client_deployment_id(deployment_id=STUB_DEPLOYMENT_ID)
        apply_command = 'cfy apply --blueprint-path {bl_path} ' \
                        '--deployment-id {dep_id} -b {bl_id} ' \
                        '--dont-skip-reinstall --reinstall-list node_a' \
                        ' --reinstall-list node_b '.format(
                            bl_path=SAMPLE_BLUEPRINT_PATH,
                            dep_id=STUB_DEPLOYMENT_ID,
                            bl_id=STUB_BLUEPRINT_ID)

        self.invoke(apply_command)

        deployment_update_mock.assert_called_with(
            deployment_id=STUB_DEPLOYMENT_ID,
            blueprint_path=None,
            inputs={},
            reinstall_list=('node_a', 'node_b'),
            skip_install=False,
            skip_uninstall=False,
            skip_reinstall=False,
            ignore_failure=False,
            install_first=False,
            preview=False,
            dont_update_plugins=False,
            workflow_id=None,
            force=False,
            include_logs=True,
            json_output=False,
            tenant_name=None,
            blueprint_id=STUB_BLUEPRINT_ID,
            visibility='tenant',
            validate=False,
            runtime_only_evaluation=False,
            auto_correct_types=False,
            reevaluate_active_statuses=False)
