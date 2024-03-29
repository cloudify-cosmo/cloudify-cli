########
# Copyright (c) 2013-2019 Cloudify Technologies Ltd. All rights reserved
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


class SitesTest(CliCommandTest):
    system_exit = {
        'err_str_segment': '2',
        'exception': SystemExit
    }

    def setUp(self):
        super(SitesTest, self).setUp()
        self.use_manager()

    def test_sites_get(self):
        self.client.sites.get = MagicMock()
        self.invoke('cfy sites get test_site')
        call_args = list(self.client.sites.get.call_args)
        self.assertEqual(call_args[0][0], 'test_site')

    def test_get_missing_name(self):
        outcome = self.invoke('cfy sites get', **self.system_exit)
        self.assertIn('missing argument', outcome.output.lower())
        self.assertIn('name', outcome.output.lower())

    def test_get_invalid_name(self):
        self.invoke(
            "cfy sites get ' ' ",
            err_str_segment='ERROR: The `name` argument contains illegal '
                            'characters',
            exception=CloudifyValidationError
        )

        self.invoke(
            "cfy sites get :bla",
            err_str_segment='ERROR: The `name` argument contains illegal '
                            'characters',
            exception=CloudifyValidationError
        )

    def test_sites_create(self):
        self.client.sites.create = MagicMock()
        self.invoke('cfy sites create test_site')
        call_args = list(self.client.sites.create.call_args)
        self.assertEqual(call_args[0][0], 'test_site')

    def test_sites_create_with_location(self):
        self.client.sites.create = MagicMock()
        self.invoke('cfy sites create test_site --location 1.0,2.0')
        call_args = list(self.client.sites.create.call_args)
        self.assertEqual(call_args[0][1], '1.0,2.0')

    def test_create_missing_name(self):
        outcome = self.invoke('cfy sites create ', **self.system_exit)
        self.assertIn('missing argument', outcome.output.lower())
        self.assertIn('name', outcome.output.lower())

    def test_create_invalid_visibility(self):
        self.invoke('cfy sites create test_site -l bla',
                    err_str_segment='Invalid visibility: `bla`',
                    exception=CloudifyCliError)

    def test_create_invalid_argument(self):
        outcome = self.invoke('cfy sites create test_site -g',
                              **self.system_exit)
        self.assertIn('No such option: -g', outcome.output)

    def test_create_invalid_location(self):
        outcome = self.invoke('cfy sites create test_site --location',
                              **self.system_exit)
        self.assertIn('Error: Option \'--location\' requires an argument',
                      outcome.output)

    def test_sites_update(self):
        self.client.sites.update = MagicMock()
        self.invoke('cfy sites update test_site')
        call_args = list(self.client.sites.update.call_args)
        self.assertEqual(call_args[0][0], 'test_site')

    def test_sites_update_with_location(self):
        self.client.sites.update = MagicMock()
        self.invoke('cfy sites update test_site --location 1.2,1.3')
        call_args = list(self.client.sites.update.call_args)
        self.assertEqual(call_args[0][1], '1.2,1.3')

    def test_sites_update_with_new_name(self):
        self.client.sites.update = MagicMock()
        self.invoke('cfy sites update test_site --new-name new_name')
        call_args = list(self.client.sites.update.call_args)
        self.assertEqual(call_args[0][3], 'new_name')

    def test_update_invalid_visibility(self):
        self.invoke('cfy sites update test_site -l bla',
                    err_str_segment='Invalid visibility: `bla`',
                    exception=CloudifyCliError)

    def test_update_invalid_location(self):
        outcome = self.invoke('cfy sites update test_site --location',
                              **self.system_exit)
        self.assertIn('Error: Option \'--location\' requires an argument',
                      outcome.output)

    def test_update_invalid_new_name(self):
        self.invoke('cfy sites update test_site --new-name :bla',
                    err_str_segment='The `new_name` argument contains illegal '
                                    'characters',
                    exception=CloudifyValidationError)

    def test_sites_delete(self):
        self.client.sites.delete = MagicMock()
        self.invoke('cfy sites delete test_site')
        call_args = list(self.client.sites.delete.call_args)
        self.assertEqual(call_args[0][0], 'test_site')

    def test_sites_list(self):
        self.client.sites.list = MagicMock()
        self.invoke('cfy sites list')

    def test_sites_invalid_command(self):
        outcome = self.invoke('cfy sites bla', **self.system_exit)
        self.assertIn('no such command', outcome.output.lower())
        self.assertIn('bla', outcome.output)
