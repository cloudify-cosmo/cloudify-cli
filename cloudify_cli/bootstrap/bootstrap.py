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

from cloudify.workflows import local

from cloudify_cli import utils


IGNORED_MODULES = (
    'worker_installer.tasks',
    'plugin_installer.tasks'
)


def _workdir():
    cloudify_dir = utils.get_init_path()
    workdir = os.path.join(cloudify_dir, 'bootstrap')
    if not os.path.isdir(workdir):
        os.mkdir(workdir)
    return workdir


def _init_env(blueprint_path,
              name,
              inputs=None):
    storage = local.FileStorage(storage_dir=_workdir())
    return local.init_env(blueprint_path,
                          name=name,
                          inputs=inputs,
                          storage=storage,
                          ignored_modules=IGNORED_MODULES)


def _load_env(name):
    storage = local.FileStorage(storage_dir=_workdir())
    return local.load_env(name=name,
                          storage=storage)


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

    provider = outputs['provider']
    provider_name = provider['name']
    provider_context = provider['context'] or {}
    provider_context['cloudify'] = outputs['cloudify']

    management_endpoint = outputs['management_endpoint']
    manager_ip = management_endpoint['manager_ip']
    manager_user = management_endpoint['manager_user']
    manager_key_path = management_endpoint['manager_key_path']

    return {
        'provider_name': provider_name,
        'provider_context': provider_context,
        'manager_ip': manager_ip,
        'manager_user': manager_user,
        'manager_key_path': manager_key_path
    }


def teardown(name='manager',
             task_retries=5,
             task_retry_interval=30,
             task_thread_pool_size=1):
    env = _load_env(name)
    env.execute('uninstall',
                task_retries=task_retries,
                task_retry_interval=task_retry_interval,
                task_thread_pool_size=task_thread_pool_size)
