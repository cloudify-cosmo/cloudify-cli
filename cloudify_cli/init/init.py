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

from cloudify.workflows import local

from cloudify_cli import utils
from cloudify_cli.commands.local import install_plugins as _install_plugins
from cloudify_cli import constants


def initialize(blueprint_path, name, storage, install_plugins=False, inputs=None):

    if install_plugins:
        _install_plugins(
            blueprint_path=blueprint_path,
            output=None
        )

    inputs = utils.json_to_dict(inputs, 'inputs')
    try:
        local.init_env(blueprint_path,
                       name=name,
                       inputs=inputs,
                       storage=storage,
                       ignored_modules=constants.IGNORED_LOCAL_WORKFLOW_MODULES)
    except ImportError as e:

        # some module is missing.
        # suggest solutions.
        e.possible_solutions = [
            "Run 'cfy local init --install-plugins'",
            "Run 'cfy local install-plugins'"
        ]
        raise e

