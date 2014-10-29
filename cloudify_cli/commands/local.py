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
Handles 'cfy local'
"""

import json
from sets import Set
import shutil
import os
from cloudify.utils import LocalCommandRunner

from cloudify.workflows import local
from dsl_parser import constants as dsl_constants
from dsl_parser.parser import parse_from_path


from cloudify_cli import exceptions
from cloudify_cli import constants
from cloudify_cli import utils
from cloudify_cli.logger import lgr

_NAME = 'local'
_STORAGE_DIR_NAME = 'local-storage'


def init(blueprint_path, inputs):
    if os.path.isdir(_storage_dir()):
        shutil.rmtree(_storage_dir())
    inputs = utils.json_to_dict(inputs, 'inputs')
    local.init_env(blueprint_path,
                   name=_NAME,
                   inputs=inputs,
                   storage=_storage(),
                   ignored_modules=constants.IGNORED_LOCAL_WORKFLOW_MODULES)
    lgr.info("Initiated {0}\nIf you make changes to the "
             "blueprint, run 'cfy local init -p {0}' again to apply them"
             .format(blueprint_path))


def execute(workflow_id,
            parameters,
            allow_custom_parameters,
            task_retries,
            task_retry_interval,
            task_thread_pool_size):
    parameters = utils.json_to_dict(parameters, 'parameters')
    env = _load_env()
    result = env.execute(workflow=workflow_id,
                         parameters=parameters,
                         allow_custom_parameters=allow_custom_parameters,
                         task_retries=task_retries,
                         task_retry_interval=task_retry_interval,
                         task_thread_pool_size=task_thread_pool_size)
    if result is not None:
        lgr.info(json.dumps(result,
                            sort_keys=True,
                            indent=2))


def outputs():
    env = _load_env()
    lgr.info(json.dumps(env.outputs() or {},
                        sort_keys=True,
                        indent=2))


def instances(node_id):
    env = _load_env()
    node_instances = env.storage.get_node_instances()
    if node_id:
        node_instances = [instance for instance in node_instances
                          if instance.node_id == node_id]
        if not node_instances:
            raise exceptions.CloudifyCliError('No node with id: {0}'
                                              .format(node_id))
    lgr.info(json.dumps(node_instances,
                        sort_keys=True,
                        indent=2))


def install_plugins(blueprint_path, output):

    requirements = _create_requirements(
        blueprint_path=blueprint_path
    )

    if output:
        utils.dump_to_file(requirements, output)
        lgr.info('requirements created successfully --> {0}'
                 .format(output))
    else:
        utils.validate_virtual_env()
        runner = LocalCommandRunner(lgr)
        for requirement in requirements:
            runner.run('pip install {0}'.format(requirement),

                       # log installation output
                       # in real time
                       stdout_pipe=False)


def _create_requirements(blueprint_path):

    parsed_dsl = parse_from_path(dsl_file_path=blueprint_path)

    sources = _plugins_to_requirements(
        blueprint_path=blueprint_path,
        plugins=parsed_dsl[
            dsl_constants.DEPLOYMENT_PLUGINS_TO_INSTALL
        ]
    )

    for node in parsed_dsl['nodes']:
        sources.update(
            _plugins_to_requirements(
                blueprint_path=blueprint_path,
                plugins=node['plugins'].values()
            )
        )
    return sources


def _plugins_to_requirements(blueprint_path, plugins):

    sources = Set()
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
                    os.path.dirname(blueprint_path),
                    'plugins',
                    source)
                sources.add(plugin_path)
    return sources


def _storage_dir():
    return os.path.join(utils.get_cwd(), _STORAGE_DIR_NAME)


def _storage():
    return local.FileStorage(storage_dir=_storage_dir())


def _load_env():
    if not os.path.isdir(_storage_dir()):
        raise exceptions.CloudifyCliError(
            '{0} has not been initialized with a blueprint. Have you called'
            ' "cfy local init" in this directory?'.format(utils.get_cwd()))
    return local.load_env(name=_NAME,
                          storage=_storage())
