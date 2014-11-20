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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import os
import tempfile

from cloudify.utils import LocalCommandRunner
from cloudify.workflows import local
from dsl_parser import constants as dsl_constants
from dsl_parser.parser import parse_from_path

from cloudify_cli import utils
from cloudify_cli import constants
from cloudify_cli.logger import get_logger
from cloudify_cli import exceptions


def initialize_blueprint(blueprint_path,
                         name,
                         storage,
                         install_plugins=False,
                         inputs=None):
    if install_plugins:
        install_blueprint_plugins(
            blueprint_path=blueprint_path
        )
    inputs = utils.json_to_dict(inputs, 'inputs')
    return local.init_env(
        blueprint_path=blueprint_path,
        name=name,
        inputs=inputs,
        storage=storage,
        ignored_modules=constants.IGNORED_LOCAL_WORKFLOW_MODULES)


def install_blueprint_plugins(blueprint_path):

    requirements = create_requirements(
        blueprint_path=blueprint_path
    )

    # validate we are inside a virtual env
    if not utils.is_virtual_env():
        raise exceptions.CloudifyCliError(
            'You must be running inside a '
            'virtualenv to install blueprint plugins')

    runner = LocalCommandRunner(get_logger())

    # dump the requirements to a file
    # and let pip install it.
    # this will utilize pip's mechanism
    # of cleanup in case an installation fails.
    output = tempfile.NamedTemporaryFile(mode='w',
                                         delete=True,
                                         suffix='.txt',
                                         prefix='requirements_')
    utils.dump_to_file(collection=requirements,
                       file_path=output.name)
    runner.run(command='pip install -r {0}'.format(output.name),
               stdout_pipe=False)


def create_requirements(blueprint_path):

    parsed_dsl = parse_from_path(dsl_file_path=blueprint_path)

    requirements = _plugins_to_requirements(
        blueprint_path=blueprint_path,
        plugins=parsed_dsl[
            dsl_constants.DEPLOYMENT_PLUGINS_TO_INSTALL
        ]
    )

    for node in parsed_dsl['nodes']:
        requirements.update(
            _plugins_to_requirements(
                blueprint_path=blueprint_path,
                plugins=node['plugins']
            )
        )

    return requirements


def _plugins_to_requirements(blueprint_path, plugins):

    sources = set()
    for plugin in plugins:
        if plugin[dsl_constants.PLUGIN_INSTALL_KEY]:
            source = plugin[
                dsl_constants.PLUGIN_SOURCE_KEY
            ]
            if '://' in source:
                # URL
                sources.add(source)
            else:
                # Local plugin (should reside under the 'plugins' dir)
                plugin_path = os.path.join(
                    os.path.abspath(os.path.dirname(blueprint_path)),
                    'plugins',
                    source)
                sources.add(plugin_path)
    return sources
