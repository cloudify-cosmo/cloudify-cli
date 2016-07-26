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

from .. import cfy

from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class InitTest(CliCommandTest):

    def test_init_initialized_directory(self):
        self.use_manager()
        self.invoke(
            'cfy init',
            err_str_segment='Environment is already initialized')

    def test_init_overwrite(self):
        # Ensuring the init with overwrite command works
        self.invoke('cfy init -r')

    def test_init_overwrite_on_initial_init(self):
        # Simply verifying the overwrite flag doesn't break the first init
        cfy.purge_dot_cloudify()
        self.invoke('cfy init -r')

    def test_no_init(self):
        cfy.purge_dot_cloudify()
        self.invoke('cfy outputs',
                    err_str_segment='Please initialize a blueprint',
                    # TODO: put back
                    # possible_solutions=[
                    #     "Run 'cfy init' in this directory"
                    # ]
                    )
