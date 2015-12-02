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
import tempfile
import urlparse
import json
import time
from io import BytesIO
from StringIO import StringIO

import fabric.api as fabric
import requests

from cloudify.workflows import local
from cloudify_cli.logger import get_logger
from cloudify_cli import common
from cloudify_cli import constants
from cloudify_cli import utils
from cloudify_cli.bootstrap.tasks import (
    PROVIDER_RUNTIME_PROPERTY,
    MANAGER_IP_RUNTIME_PROPERTY,
    MANAGER_USER_RUNTIME_PROPERTY,
    MANAGER_KEY_PATH_RUNTIME_PROPERTY,
    REST_PORT)
from cloudify_cli.exceptions import CloudifyBootstrapError


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


def load_env(name='manager'):
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


def _handle_provider_context(agent_remote_key_path,
                             fabric_env,
                             manager_node,
                             manager_node_instance):
    if 'provider_context' in manager_node_instance.runtime_properties:
        provider_context = manager_node_instance.runtime_properties[
            'provider_context']
    else:
        provider_context = None
    _upload_provider_context(
        agent_remote_key_path, fabric_env, manager_node,
        manager_node_instance, provider_context=provider_context)
    provider_context = \
        manager_node_instance.runtime_properties[
            'manager_provider_context']
    return provider_context


def _handle_agent_key_file(fabric_env, manager_node):
    # these should be changed to allow receiving the
    # paths from the blueprint.
    agent_remote_key_path = manager_node.properties.get(
        'agent_remote_key_path', constants.AGENT_REMOTE_KEY_PATH)
    agent_local_key_path = manager_node.properties.get(
        'agent_local_key_path')
    agent_remote_key_path = _copy_agent_key(agent_local_key_path,
                                            agent_remote_key_path,
                                            fabric_env)
    return agent_remote_key_path


def bootstrap(blueprint_path,
              name='manager',
              inputs=None,
              task_retries=5,
              task_retry_interval=30,
              task_thread_pool_size=1,
              install_plugins=False):

    def get_protocol(rest_port):
        return constants.SECURED_PROTOCOL \
            if str(rest_port) == str(constants.SECURED_REST_PORT) \
            else constants.DEFAULT_PROTOCOL

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
        manager_ip = env.outputs()['manager_ip']
        manager_user = manager_node.properties['ssh_user']
        manager_key_path = manager_node.properties['ssh_key_filename']
        rest_port = manager_node_instance.runtime_properties[REST_PORT]

        fabric_env = {
            "host_string": manager_ip,
            "user": manager_user,
            "key_filename": manager_key_path
        }

        agent_remote_key_path = _handle_agent_key_file(fabric_env,
                                                       manager_node)

        provider_context = _handle_provider_context(
            agent_remote_key_path=agent_remote_key_path,
            fabric_env=fabric_env,
            manager_node=manager_node,
            manager_node_instance=manager_node_instance)

        _upload_resources(manager_node, fabric_env, manager_ip, rest_port,
                          get_protocol(rest_port))

    protocol = get_protocol(rest_port)

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


def recover(snapshot_path,
            name='manager',
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

    manager_ip = env.outputs()['manager_ip']
    manager_node = env.storage.get_node('manager_configuration')
    manager_node_instance = env.storage.get_node_instance(
        manager_node_instance_id)
    manager_user = manager_node.properties['ssh_user']
    manager_key_path = manager_node.properties['ssh_key_filename']

    fabric_env = {
        "host_string": manager_ip,
        "user": manager_user,
        "key_filename": manager_key_path
    }

    agent_remote_key_path = _handle_agent_key_file(fabric_env,
                                                   manager_node)

    _handle_provider_context(
        agent_remote_key_path=agent_remote_key_path,
        fabric_env=fabric_env,
        manager_node=manager_node,
        manager_node_instance=manager_node_instance)

    logger = get_logger()
    client = utils.get_rest_client(manager_ip)
    snapshot_id = 'restored-snapshot'
    logger.info("Uploading snapshot '{0}' to "
                "management server {1} as {2}"
                .format(snapshot_path.name, manager_ip, snapshot_id))
    client.snapshots.upload(snapshot_path.name, snapshot_id)

    logger.info("Restoring snapshot '{0}'..."
                .format(snapshot_id))
    execution = client.snapshots.restore(snapshot_id, True)

    # waiting for snapshot restoration
    attempts = 5
    start_time = time.time()
    wait_time = 60 * 1
    while client.executions.get(
            execution.id).status not in execution.END_STATES:
        if time.time() > start_time + wait_time:
            if attempts == 0:
                raise RuntimeError('Failed to restore snapshot '
                                   'after {0} attempts'.format(attempts))
            attempts -= 1
            start_time = time.time()
            wait_time *= 2
            logger.info('Waiting {0} seconds for '
                        'snapshot restoration'.format(wait_time))
        time.sleep(5)
    if execution.status == execution.FAILED:
        raise RuntimeError('Failed to restore '
                           'snapshot {0}'.format(snapshot_id))
    if execution.status == execution.TERMINATED:
        logger.info('Successfully restored snapshot {0}'.format(snapshot_id))
    client.snapshots.delete(snapshot_id)


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
        fabric.put(agent_local_key_path, agent_remote_key_path, use_sudo=True)
    return agent_remote_key_path


def _upload_resources(manager_node, fabric_env, management_ip, rest_port,
                      protocol):
    """
    Uploads resources supplied in the manager blueprint. uses both fabric for
    the dsl_resources, and the upload plugins mechanism for plugin_resources.

    :param manager_node: The manager node from which to retrieve the
    properties from.
    :param fabric_env: fabric env in order to upload the dsl_resources.
    :param management_ip: used to retrieve rest client for the the manager.
    :param rest_port: used to retrieve rest client for the the manager.
    :param protocol: used to retrieve rest client for the the manager.
    """

    upload_resources = \
        manager_node.properties['cloudify'].get('upload_resources', {})

    # upload the plugin using CLI upload command
    rest_client = utils.get_rest_client(management_ip, rest_port, protocol)

    # This import is necessary to prevent from utils importing plugins, which
    # will cause a cyclic import. Another way is to forgo the validate part
    from cloudify_cli.commands import plugins
    temp_dir = tempfile.mkdtemp()
    try:
        for plugin_archive_source in \
                upload_resources.get('plugin_resources', ()):
            plugin_archive_path = \
                _get_resource_into_dir(temp_dir, plugin_archive_source)
            utils.upload_plugin(file(plugin_archive_path), management_ip,
                                rest_client, plugins.validate)

        # uploading dsl resources
        remote_plugins_folder = '/opt/manager/resources/'

        for dsl_resource in upload_resources.get('dsl_resources', ()):

            plugin_local_yaml_path = dsl_resource.get('source_path')
            plugin_remote_yaml_path = dsl_resource.get('destination_path')

            if not plugin_local_yaml_path or not plugin_remote_yaml_path:
                missing_fields = []
                if plugin_local_yaml_path is None:
                    missing_fields.append('source_path')
                if plugin_remote_yaml_path is None:
                    missing_fields.append('destination_path')

                raise \
                    CloudifyBootstrapError('The following fields are missing: '
                                           '{0}.'
                                           .format(','.join(missing_fields)))

            if plugin_remote_yaml_path.startswith('/'):
                plugin_remote_yaml_path = plugin_remote_yaml_path[1:]

            plugin_local_yaml_path = \
                _get_resource_into_dir(temp_dir, plugin_local_yaml_path)

            # copy plugin's yaml file to the manager's fileserver
            with fabric.settings(**fabric_env):

                remote_plugin_folder_path = \
                    "{0}{1}".format(remote_plugins_folder,
                                    os.path.dirname(plugin_remote_yaml_path))
                fabric.run('sudo mkdir -p {0}'.format(
                    remote_plugin_folder_path))

                # Uploading the plugin file
                remote_plugin_path = "{0}{1}".format(remote_plugins_folder,
                                                     plugin_remote_yaml_path)
                fabric.put(plugin_local_yaml_path, remote_plugin_path,
                           use_sudo=True)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _get_resource_into_dir(destination_dir, resource_source_path):
    """
    Copies a given path into the destination dir. The path could refer to
    a local file or a remote url. NOTE: If two files shares the same name,
    the old file would be overwritten.
    :param destination_dir: The dir to write the resource into.
    :param resource_source_path: A path to the resource.
    :return: the path to the newly copied resource.
    """
    logger = get_logger()
    temp_file_path = os.path.join(destination_dir,
                                  resource_source_path.split('/')[-1])

    parts = urlparse.urlsplit(resource_source_path)

    if not parts.scheme or not parts.netloc:
        if not os.path.isabs(resource_source_path):
            resource_source_path = os.path.abspath(resource_source_path)
        logger.info('Copying from {0} to {1}'
                    .format(resource_source_path, temp_file_path))
        shutil.copyfile(resource_source_path, temp_file_path)
        logger.info('Done copying')
    else:
        try:
            logger.info('Downloading from {0} to {1}'
                        .format(resource_source_path, temp_file_path))
            resource_request = requests.get(resource_source_path, stream=True)
        except requests.exceptions.RequestException:
            msg = '{0} is neither a valid local path nor a valid url' \
                .format(resource_source_path)
            raise CloudifyBootstrapError(msg)
        if resource_request.status_code == 200:
            with open(temp_file_path, 'wb') as f:
                resource_request.raw.decode_content = True
                shutil.copyfileobj(resource_request.raw, f)
            resource_request.close()
        else:
            msg = "The url {0} doesn't exists".format(resource_source_path)
            raise CloudifyBootstrapError(msg)
        logger.info('Download complete')

    return temp_file_path
