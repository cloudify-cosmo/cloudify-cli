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

from mock import MagicMock
from .test_base import CliCommandTest
from cloudify_cli.exceptions import CloudifyValidationError, CloudifyCliError


class SecretsTest(CliCommandTest):
    def setUp(self):
        super(SecretsTest, self).setUp()
        self.use_manager()

    def test_get_secrets_missing_key(self):
        outcome = self.invoke(
            'cfy secrets get',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('Missing argument "key"', outcome.output)

    def test_get_secrets_invalid_key(self):
        self.invoke(
            "cfy secrets get ' ' ",
            err_str_segment='ERROR: The `key` argument contains illegal '
                            'characters',
            exception=CloudifyValidationError
        )

    def test_create_secrets_missing_value(self):
        self.invoke(
            'cfy secrets create key',
            err_str_segment='Failed to create secret key. '
                            'Missing option --secret-string or secret-file.',
            exception=CloudifyCliError
        )

    def test_secrets_set_global(self):
        self.client.secrets.set_global = MagicMock()
        self.invoke('cfy secrets set-global a-secret-key')

    def test_secrets_set_visibility(self):
        self.client.secrets.set_visibility = MagicMock()
        self.invoke('cfy secrets set-visibility a-secret-key -l global')

    def test_secrets_set_visibility_invalid_argument(self):
        self.invoke('cfy secrets set-visibility a-secret-key -l private',
                    err_str_segment='Invalid visibility: `private`',
                    exception=CloudifyCliError)

    def test_secrets_set_visibility_missing_argument(self):
        outcome = self.invoke('cfy secrets set-visibility a-secret-key',
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn('Missing option "-l" / "--visibility"',
                      outcome.output)

    def test_secrets_set_visibility_wrong_argument(self):
        outcome = self.invoke('cfy secrets set-visibility a-secret-key -g',
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn('Error: no such option: -g', outcome.output)

    def test_secrets_create_invalid_argument(self):
        self.invoke('cfy secrets create a-secret-key -l bla',
                    err_str_segment='Invalid visibility: `bla`',
                    exception=CloudifyCliError)

    def test_secrets_create_with_visibility(self):
        self.client.secrets.create = MagicMock()
        self.invoke('cfy secrets create a-secret-key -l private -s hello')

    def test_secrets_create_mutually_exclusive_arguments(self):
        outcome = self.invoke(
            'cfy secrets create a-secret-key -s hello -f file',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('mutually exclusive with arguments:', outcome.output)
