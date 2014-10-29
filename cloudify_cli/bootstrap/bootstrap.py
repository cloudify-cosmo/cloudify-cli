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
import shutil

from cloudify.workflows import local

from cloudify_cli import constants
from cloudify_cli import utils
from cloudify_cli.bootstrap.tasks import (
    PROVIDER_RUNTIME_PROPERTY,
    MANAGER_USER_RUNTIME_PROPERTY,
    MANAGER_KEY_PATH_RUNTIME_PROPERTY
)


def _workdir():
    cloudify_dir = utils.get_init_path()
    workdir = os.path.join(cloudify_dir, 'bootstrap')
    if not os.path.isdir(workdir):
        os.mkdir(workdir)
    return workdir


def _init_env(blueprint_path,
              name,
              inputs=None,
              use_file_storage=True):
    storage = local.FileStorage(storage_dir=_workdir()) if use_file_storage \
        else None
    return local.init_env(
        blueprint_path,
        name=name,
        inputs=inputs,
        storage=storage,
        ignored_modules=constants.IGNORED_LOCAL_WORKFLOW_MODULES)


def load_env(name):
    storage = local.FileStorage(storage_dir=_workdir())
    return local.load_env(name=name,
                          storage=storage)


def bootstrap_validation(blueprint_path,
                         name='manager',
                         inputs=None,
                         task_retries=5,
                         task_retry_interval=30,
                         task_thread_pool_size=1):
    inputs = inputs or {}
    env = _init_env(blueprint_path,
                    name=name,
                    inputs=inputs,
                    use_file_storage=False)

    env.execute(workflow='execute_operation',
                parameters={'operation':
                            'cloudify.interfaces.validation.creation'},
                task_retries=task_retries,
                task_retry_interval=task_retry_interval,
                task_thread_pool_size=task_thread_pool_size)


def bootstrap(blueprint_path,
              name='manager',
              inputs=None,
              task_retries=5,
              task_retry_interval=30,
              task_thread_pool_size=1):
    inputs = inputs or {}
    env = _init_env(blueprint_path,
                    name=name,
                    inputs=inputs)

    env.execute(workflow='install',
                task_retries=task_retries,
                task_retry_interval=task_retry_interval,
                task_thread_pool_size=task_thread_pool_size)

    outputs = env.outputs()
    manager_ip = outputs['manager_ip']

    node_instances = env.storage.get_node_instances()
    nodes_by_id = {node.id: node for node in env.storage.get_nodes()}
    manager_node_instance = \
        next(node_instance for node_instance in node_instances if
             'cloudify.nodes.CloudifyManager' in
             nodes_by_id[node_instance.node_id].type_hierarchy)
    provider_context = \
        manager_node_instance.runtime_properties[PROVIDER_RUNTIME_PROPERTY]
    manager_user = \
        manager_node_instance.runtime_properties[MANAGER_USER_RUNTIME_PROPERTY]
    manager_key_path = manager_node_instance.runtime_properties[
        MANAGER_KEY_PATH_RUNTIME_PROPERTY]

    return {
        'provider_name': 'provider',
        'provider_context': provider_context,
        'manager_ip': manager_ip,
        'manager_user': manager_user,
        'manager_key_path': manager_key_path
    }


def teardown(name='manager',
             task_retries=5,
             task_retry_interval=30,
             task_thread_pool_size=1):
    env = load_env(name)
    env.execute('uninstall',
                task_retries=task_retries,
                task_retry_interval=task_retry_interval,
                task_thread_pool_size=task_thread_pool_size)

    # deleting local environment data
    shutil.rmtree(_workdir())
