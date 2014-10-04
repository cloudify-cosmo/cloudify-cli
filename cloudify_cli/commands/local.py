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
import shutil
import os

from cloudify.workflows import local

from cloudify_cli import exceptions
from cloudify_cli import constants
from cloudify_cli import utils
from cloudify_cli.logger import lgr


_storage_dir = os.path.join(utils.get_cwd(), '.storage')
_name = 'local'


def init(blueprint_path, inputs):
    if os.path.isdir(_storage_dir):
        shutil.rmtree(_storage_dir)
    inputs = utils.json_to_dict(inputs, 'inputs')
    local.init_env(blueprint_path,
                   name=_name,
                   inputs=inputs,
                   storage=_storage(),
                   ignored_modules=constants.IGNORED_LOCAL_WORKFLOW_MODULES)


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


def _storage():
    return local.FileStorage(storage_dir=_storage_dir)


def _load_env():
    if not os.path.isdir(_storage_dir):
        raise exceptions.CloudifyCliError(
            '{0} has not been initialized with a blueprint. Have you called'
            ' "cfy local init" in this directory?'.format(utils.get_cwd()))
    return local.load_env(name=_name,
                          storage=_storage())
