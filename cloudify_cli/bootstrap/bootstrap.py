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
import base64
import tarfile
from io import BytesIO
from StringIO import StringIO
import fabric.api as fabric
import json

from cloudify.workflows import local

from cloudify_cli import common
from cloudify_cli import constants
from cloudify_cli import utils
from cloudify_cli.bootstrap.tasks import (
    PROVIDER_RUNTIME_PROPERTY,
    MANAGER_IP_RUNTIME_PROPERTY,
    MANAGER_USER_RUNTIME_PROPERTY,
    MANAGER_KEY_PATH_RUNTIME_PROPERTY,
    REST_PORT)


def _workdir():
    cloudify_dir = utils.get_init_path()
    workdir = os.path.join(cloudify_dir, 'bootstrap')
    if not os.path.isdir(workdir):
        os.mkdir(workdir)
    return workdir


def delete_workdir():
    cloudify_dir = utils.get_init_path()
    workdir = os.path.join(cloudify_dir, 'bootstrap')
    if os.path.exists(workdir):
        shutil.rmtree(workdir)


def load_env(name='manager_configuration'):
    storage = local.FileStorage(storage_dir=_workdir())
    return local.load_env(name=name,
                          storage=storage)


def bootstrap_validation(blueprint_path,
                         name='manager',
                         inputs=None,
                         task_retries=5,
                         task_retry_interval=30,
                         task_thread_pool_size=1,
                         install_plugins=False,
                         resolver=None):
    try:
        env = common.initialize_blueprint(
            blueprint_path,
            name=name,
            inputs=inputs,
            storage=None,
            install_plugins=install_plugins,
            resolver=resolver
        )
    except ImportError as e:
        e.possible_solutions = [
            "Run 'cfy local install-plugins -p {0}'"
            .format(blueprint_path),
            "Run 'cfy bootstrap --install-plugins -p {0}'"
            .format(blueprint_path)
        ]
        raise

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
              task_thread_pool_size=1,
              install_plugins=False):

    storage = local.FileStorage(storage_dir=_workdir())
    try:
        env = common.initialize_blueprint(
            blueprint_path,
            name=name,
            inputs=inputs,
            storage=storage,
            install_plugins=install_plugins,
            resolver=utils.get_import_resolver()
        )
    except ImportError as e:
        e.possible_solutions = [
            "Run 'cfy local install-plugins -p {0}'"
            .format(blueprint_path),
            "Run 'cfy bootstrap --install-plugins -p {0}'"
            .format(blueprint_path)
        ]
        raise

    env.execute(workflow='install',
                task_retries=task_retries,
                task_retry_interval=task_retry_interval,
                task_thread_pool_size=task_thread_pool_size)

    nodes = env.storage.get_nodes()
    node_instances = env.storage.get_node_instances()
    nodes_by_id = {node.id: node for node in nodes}

    try:
        manager_node_instance = \
            next(node_instance for node_instance in node_instances if
                 'cloudify.nodes.CloudifyManager' in
                 nodes_by_id[node_instance.node_id].type_hierarchy)
    except Exception:
        manager_node_instance = \
            next(node_instance for node_instance in node_instances if
                 'cloudify.nodes.MyCloudifyManager' in
                 nodes_by_id[node_instance.node_id].type_hierarchy)
        manager_node = nodes_by_id['manager_configuration']

    if manager_node_instance.runtime_properties.get('provider'):
        provider_context = \
            manager_node_instance.runtime_properties[
                PROVIDER_RUNTIME_PROPERTY]
        manager_ip = \
            manager_node_instance.runtime_properties[
                MANAGER_IP_RUNTIME_PROPERTY]
        manager_user = \
            manager_node_instance.runtime_properties[
                MANAGER_USER_RUNTIME_PROPERTY]
        manager_key_path = manager_node_instance.runtime_properties[
            MANAGER_KEY_PATH_RUNTIME_PROPERTY]
        rest_port = \
            manager_node_instance.runtime_properties[REST_PORT]
    else:
        manager_ip = \
            manager_node_instance.runtime_properties['manager_host_public_ip']
        manager_user = manager_node.properties['ssh_user']
        manager_key_path = manager_node.properties['ssh_key_filename']
        rest_port = 80

        # these should be changed to allow receiving the
        # paths from the blueprint.
        agent_remote_key_path = manager_node.properties.get(
            'agent_remote_key_path', constants.AGENT_REMOTE_KEY_PATH)
        agent_local_key_path = manager_node.properties.get(
            'agent_local_key_path')
        fabric_env = {
            "host_string": manager_ip,
            "user": manager_user,
            "key_filename": manager_key_path
        }
        agent_remote_key_path = _copy_agent_key(agent_local_key_path,
                                                agent_remote_key_path,
                                                fabric_env)
        _upload_provider_context(
            agent_remote_key_path, fabric_env, manager_node,
            manager_node_instance, provider_context=False)

        provider_context = \
            manager_node_instance.runtime_properties[
                'manager_provider_context']

    protocol = constants.SECURED_PROTOCOL \
        if rest_port == constants.SECURED_REST_PORT \
        else constants.DEFAULT_PROTOCOL

    return {
        'provider_name': 'provider',
        'provider_context': provider_context,
        'manager_ip': manager_ip,
        'manager_user': manager_user,
        'manager_key_path': manager_key_path,
        'rest_port': rest_port,
        'protocol': protocol
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


def recover(name='manager',
            task_retries=5,
            task_retry_interval=30,
            task_thread_pool_size=1):
    env = load_env(name)
    with env.storage.payload() as payload:
        manager_node_instance_id = payload['manager_node_instance_id']

    env.execute('heal',
                parameters={'node_instance_id': manager_node_instance_id},
                task_retries=task_retries,
                task_retry_interval=task_retry_interval,
                task_thread_pool_size=task_thread_pool_size)


# Temp workaround to allow teardown and recovery on different clients
# assumes deployment name is manager
def dump_manager_deployment():
    name = 'manager'
    file_obj = BytesIO()
    output = StringIO()
    with tarfile.open(fileobj=file_obj, mode='w:gz') as tar:
        tar.add(os.path.join(_workdir(), name),
                arcname=name)
    file_obj.seek(0)
    base64.encode(file_obj, output)
    return output.getvalue()


def read_manager_deployment_dump_if_needed(manager_deployment_dump):
    name = 'manager'
    if not manager_deployment_dump:
        return False
    if os.path.exists(os.path.join(_workdir(), name)):
        return False
    dump_input = StringIO(manager_deployment_dump)
    dump_input.seek(0)
    file_obj = BytesIO()
    base64.decode(dump_input, file_obj)
    file_obj.seek(0)
    with tarfile.open(fileobj=file_obj, mode='r:gz') as tar:
        tar.extractall(_workdir())
    return True


def _upload_provider_context(remote_agents_private_key_path, fabric_env,
                             manager_node, manager_node_instance,
                             provider_context=None, update_context=False):
    provider_context = provider_context or {}
    cloudify_configuration = manager_node.properties['cloudify']
    cloudify_configuration['cloudify_agent']['agent_key_path'] = \
        remote_agents_private_key_path
    provider_context['cloudify'] = cloudify_configuration
    manager_node_instance.runtime_properties['manager_provider_context'] = \
        provider_context

    # 'manager_deployment' is used when running 'cfy use ...'
    # and then calling teardown or recover. Anyway, this code will only live
    # until we implement the fuller feature of uploading manager blueprint
    # deployments to the manager.
    cloudify_configuration['manager_deployment'] = \
        _dump_manager_deployment(manager_node_instance)

    remote_provider_context_file = '/tmp/provider-context.json'
    provider_context_json_file = StringIO()
    full_provider_context = {
        'name': 'provider',
        'context': provider_context
    }
    json.dump(full_provider_context, provider_context_json_file)

    request_params = '?update={0}'.format(update_context)
    upload_provider_context_cmd = \
        'curl --fail -XPOST localhost:8101/api/{0}/provider/context{1} -H ' \
        '"Content-Type: application/json" -d @{2}'.format(
            constants.API_VERSION, request_params,
            remote_provider_context_file)

    # placing provider context file in the manager's host
    with fabric.settings(**fabric_env):
        fabric.put(provider_context_json_file, remote_provider_context_file)
        # might need always_use_pty=True
        # uploading the provider context to the REST service
        fabric.run(upload_provider_context_cmd)


def _dump_manager_deployment(manager_node_instance):
    # explicitly write the manager node instance id to local storage
    env = load_env('manager')
    with env.storage.payload() as payload:
        payload['manager_node_instance_id'] = manager_node_instance.id

    # explicitly flush runtime properties to local storage
    manager_node_instance.update()
    return dump_manager_deployment()


def _copy_agent_key(agent_local_key_path, agent_remote_key_path,
                    fabric_env):
    if not agent_local_key_path:
        return None
    agent_local_key_path = os.path.expanduser(agent_local_key_path)
    with fabric.settings(**fabric_env):
        fabric.put(agent_local_key_path, agent_remote_key_path)
    return agent_remote_key_path
