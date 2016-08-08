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

from dsl_parser.constants import HOST_TYPE
from .constants import BLUEPRINTS_DIR
from .test_base import CliCommandTest


class LocalTest(CliCommandTest):

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
