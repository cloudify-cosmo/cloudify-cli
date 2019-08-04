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
import os

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

    def test_secrets_export_invalid_password_length(self):
        self.invoke('cfy secrets export -p 1234567',
                    err_str_segment='ERROR: Passphrase must contain at least '
                                    '8 characters.',
                    exception=CloudifyValidationError)

    def test_secrets_export_valid_password(self):
        self.client.secrets.export = MagicMock(return_value={'key': '0'})
        self.invoke('cfy secrets export -p 12345678')
        call_args = self.client.secrets.export.call_args
        self.assertIn('_passphrase', call_args[1])
        self.assertEqual(call_args[1]['_passphrase'], '12345678')
        os.system('rm secrets.json')

    def test_secrets_export_empty_password(self):
        self.invoke("cfy secrets export -p ' '",
                    err_str_segment='ERROR: Passphrase must contain at least'
                                    ' 8 characters.',
                    exception=CloudifyValidationError)

    def test_secrets_export_mutually_exclusive_tenant_all_tenants(self):
        outcome = self.invoke('cfy secrets export -t default_tenant -a '
                              '--non-encrypted',
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn(
            '`tenant_name` is mutually exclusive with arguments: '
            '[all_tenants]', outcome.output)

    def test_secrets_export_all_tenants(self):
        self.client.secrets.export = MagicMock(return_value={'key': '1'})
        self.invoke('cfy secrets export -a --non-encrypted')
        call_args = self.client.secrets.export.call_args
        self.assertIn('_all_tenants', call_args[1])
        self.assertEqual(call_args[1]['_all_tenants'], True)
        os.system('rm secrets.json')

    def test_secrets_export_invalid_visibility(self):
        self.invoke('cfy secrets export -l hi --non-encrypted',
                    err_str_segment="Invalid visibility: `hi`. "
                                    "Valid visibility's values are: "
                                    "['private', 'tenant', 'global']")

    def test_secrets_export_with_visibility(self):
        self.client.secrets.export = MagicMock(return_value={'key': '2'})
        self.invoke('cfy secrets export -l global --non-encrypted')
        call_args = self.client.secrets.export.call_args
        self.assertIn('visibility', call_args[1])
        self.assertEqual(call_args[1]['visibility'], 'global')
        os.system('rm secrets.json')

    def test_secrets_export_filter_by(self):
        self.client.secrets.export = MagicMock(return_value={'key': '3'})
        self.invoke('cfy secrets export --filter-by key --non-encrypted')
        call_args = self.client.secrets.export.call_args
        self.assertIn('_search', call_args[1])
        self.assertEqual(call_args[1]['_search'], 'key')
        os.system('rm secrets.json')

    def test_secrets_import_mutually_exclusive_passphrase_non_encrypted(self):
        outcome = self.invoke('cfy secrets import -p 12345678'
                              ' --non-encrypted',
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn(
            '`non_encrypted` is mutually exclusive with arguments:'
            ' [passphrase]', outcome.output)

    def test_secrets_import_encryption_given(self):
        os.system('touch secrets.json')
        self.invoke('cfy secrets import -i secrets.json',
                    err_str_segment="Please provide one of the options:")
        os.system('rm secrets.json')
