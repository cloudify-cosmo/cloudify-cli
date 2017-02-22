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
import copy
import shutil
import base64
import random
import string
import tarfile
import tempfile
import urlparse
from io import BytesIO
from functools import partial
from StringIO import StringIO

import requests
from retrying import retry
import fabric.api as fabric

from cloudify.workflows import local
from cloudify.exceptions import RecoverableError

from .. import env
from .. import constants
from ..config import config
from ..logger import get_logger
from ..local import initialize_blueprint
from ..exceptions import CloudifyBootstrapError

PROVIDER_RUNTIME_PROPERTY = 'provider'
MANAGER_IP_RUNTIME_PROPERTY = 'manager_ip'
SSH_USER_RUNTIME_PROPERTY = 'ssh_user'
SSH_PORT_RUNTIME_PROPERTY = 'ssh_port'
SSH_KEY_PATH_RUNTIME_PROPERTY = 'ssh_key_path'

MANAGER_DEPLOYMENT_ARCHIVE_IGNORED_FILES = ['.git']
MAX_MANAGER_DEPLOYMENT_SIZE = 50 * (10 ** 6)  # 50MB

_ENV_NAME = 'manager'


def _workdir():
    active_profile = env.get_active_profile()
    profile_dir = env.get_profile_dir(active_profile)
    workdir = os.path.join(profile_dir, 'bootstrap')
    if not os.path.isdir(workdir):
        os.makedirs(workdir)
    return workdir


def delete_workdir():
    active_profile = env.get_active_profile()
    profile_dir = env.get_profile_dir(active_profile)
    workdir = os.path.join(profile_dir, 'bootstrap')
    if os.path.isdir(workdir):
        shutil.rmtree(workdir)


def load_env(name=_ENV_NAME):
    storage = local.FileStorage(storage_dir=_workdir())
    return local.load_env(name=name, storage=storage)


def blueprint_archive_filter_func(tarinfo):
    if any((tarinfo.name.endswith(ignored_file) for ignored_file in
            MANAGER_DEPLOYMENT_ARCHIVE_IGNORED_FILES)):
        # ignoring file when creating the archive
        return None
    return tarinfo


def tar_manager_deployment(manager_deployment_path=None):
    name = _ENV_NAME
    file_obj = BytesIO()
    with tarfile.open(fileobj=file_obj, mode='w:gz') as tar:
        tar.add(manager_deployment_path or os.path.join(_workdir(), name),
                arcname=name,
                filter=blueprint_archive_filter_func)
    file_obj.seek(0)
    return file_obj


# Temp workaround to allow teardown and recovery on different clients
# assumes deployment name is manager
def dump_manager_deployment():
    archive_obj = tar_manager_deployment()
    output = StringIO()
    base64.encode(archive_obj, output)
    return output.getvalue()


def read_manager_deployment_dump_if_needed(manager_deployment_dump):
    name = _ENV_NAME
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


def validate_manager_deployment_size(blueprint_path):
    blueprint_folder = os.path.dirname(os.path.abspath(blueprint_path))
    # checking for the size of the blueprint's folder when archived
    archive_obj = tar_manager_deployment(blueprint_folder)
    manager_dep_size = len(archive_obj.getvalue())
    if manager_dep_size > MAX_MANAGER_DEPLOYMENT_SIZE:
        raise CloudifyBootstrapError(
            "The manager blueprint's folder is above the maximum allowed size "
            "when archived (size is {0} bytes; max is {1}); Please ensure the "
            "manager blueprint's folder doesn't contain any unnecessary files "
            "or directories".format(manager_dep_size,
                                    MAX_MANAGER_DEPLOYMENT_SIZE))


def bootstrap_validation(blueprint_path,
                         name='manager',
                         inputs=None,
                         task_retries=5,
                         task_retry_interval=30,
                         task_thread_pool_size=1,
                         install_plugins=False,
                         resolver=None):
    validate_manager_deployment_size(blueprint_path=blueprint_path)

    try:
        working_env = initialize_blueprint(
            blueprint_path,
            name=name,
            inputs=inputs,
            storage=None,
            install_plugins=install_plugins,
            resolver=resolver
        )
    except ImportError as e:
        e.possible_solutions = [
            "Run 'cfy bootstrap --install-plugins {0}'".format(blueprint_path),
            "Run 'cfy init --install-plugins {0}'".format(blueprint_path)
        ]
        raise

    working_env.execute(workflow='execute_operation',
                        parameters={
                            'operation':
                                'cloudify.interfaces.validation.creation'},
                        task_retries=task_retries,
                        task_retry_interval=task_retry_interval,
                        task_thread_pool_size=task_thread_pool_size)


def _perform_sanity(working_env,
                    manager_ip,
                    fabric_env,
                    task_retries=5,
                    task_retry_interval=30,
                    task_thread_pool_size=1):
    working_env.execute(workflow='execute_operation',
                        parameters={'operation':
                                    'cloudify.interfaces.lifecycle.start',
                                    'node_ids': ['sanity'],
                                    'allow_kwargs_override': 'true',
                                    'operation_kwargs':
                                        {'run_sanity': 'true',
                                         'manager_ip': manager_ip,
                                         'fabric_env': fabric_env}},
                        allow_custom_parameters=True,
                        task_retries=task_retries,
                        task_retry_interval=task_retry_interval,
                        task_thread_pool_size=task_thread_pool_size)


def _handle_provider_context(rest_client,
                             remote_agents_private_key_path,
                             manager_node,
                             manager_node_instance):
    provider_context = manager_node_instance.runtime_properties.get(
        'provider_context', {})
    cloudify_configuration = manager_node.properties['cloudify']
    cloudify_configuration['cloudify_agent']['agent_key_path'] = \
        remote_agents_private_key_path
    broker_ip = manager_node_instance.runtime_properties.get('broker_ip', '')
    cloudify_configuration['cloudify_agent']['broker_ip'] = broker_ip
    provider_context['cloudify'] = cloudify_configuration
    manager_node_instance.runtime_properties['manager_provider_context'] = \
        provider_context
    # 'manager_deployment' is used when running 'cfy profiles use ...'
    # and then calling teardown or recover. Anyway, this code will only live
    # until we implement the fuller feature of uploading manager blueprint
    # deployments to the manager.
    cloudify_configuration['manager_deployment'] = \
        _dump_manager_deployment(manager_node_instance)

    rest_client.manager.create_context(name='provider',
                                       context=provider_context)
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
              install_plugins=False,
              skip_sanity=False):
    storage = local.FileStorage(storage_dir=_workdir())
    try:
        working_env = initialize_blueprint(
            blueprint_path,
            name=name,
            inputs=inputs,
            storage=storage,
            install_plugins=install_plugins,
            resolver=config.get_import_resolver()
        )
    except ImportError as e:
        e.possible_solutions = [
            "Run 'cfy install-plugins {0}'".format(blueprint_path),
            "Run 'cfy bootstrap {0} --install-plugins'".format(blueprint_path)
        ]
        raise

    working_env.execute(workflow='install',
                        task_retries=task_retries,
                        task_retry_interval=task_retry_interval,
                        task_thread_pool_size=task_thread_pool_size)

    nodes = working_env.storage.get_nodes()
    node_instances = working_env.storage.get_node_instances()
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

    rest_port = manager_node_instance.runtime_properties[
        constants.REST_PORT_RUNTIME_PROPERTY]
    rest_protocol = manager_node_instance.runtime_properties[
        constants.REST_PROTOCOL_RUNTIME_PROPERTY]

    if manager_node_instance.runtime_properties.get('provider'):
        provider_context = \
            manager_node_instance.runtime_properties[
                PROVIDER_RUNTIME_PROPERTY]
        manager_ip = \
            manager_node_instance.runtime_properties[
                MANAGER_IP_RUNTIME_PROPERTY]
        ssh_user = \
            manager_node_instance.runtime_properties[
                SSH_USER_RUNTIME_PROPERTY]
        ssh_port = \
            manager_node_instance.runtime_properties[
                SSH_PORT_RUNTIME_PROPERTY]
        ssh_key_path = manager_node_instance.runtime_properties[
            SSH_KEY_PATH_RUNTIME_PROPERTY]
    else:
        manager_ip = working_env.outputs()['manager_ip']
        ssh_user = manager_node.properties['ssh_user']
        ssh_port = manager_node.properties['ssh_port']
        ssh_key_path = manager_node.properties['ssh_key_filename']

        fabric_env = build_fabric_env(manager_ip,
                                      ssh_user,
                                      ssh_port,
                                      ssh_key_path)

        agent_remote_key_path = _handle_agent_key_file(fabric_env,
                                                       manager_node)
        # dump public rest certificate to a local file for future
        # communication with the rest server
        rest_public_cert = working_env.outputs()[
            'rest_server_public_certificate']
        if rest_public_cert:
            cert_path = env.get_default_rest_cert_local_path()
            with open(cert_path, 'w') as cert_file:
                cert_file.write(rest_public_cert)

        rest_client = env.get_rest_client(
            rest_host=manager_ip,
            rest_port=rest_port,
            rest_protocol=rest_protocol,
            username=inputs['admin_username'],
            password=inputs['admin_password'],
            skip_version_check=True,
            tenant_name=constants.DEFAULT_TENANT_NAME)

        provider_context = _handle_provider_context(
            rest_client=rest_client,
            remote_agents_private_key_path=agent_remote_key_path,
            manager_node=manager_node,
            manager_node_instance=manager_node_instance)

        _upload_resources(
            manager_node,
            fabric_env,
            rest_client,
            task_retries,
            task_retry_interval)

        if not skip_sanity:
            _perform_sanity(working_env=working_env,
                            manager_ip=manager_ip,
                            fabric_env=fabric_env,
                            task_retries=task_retries,
                            task_retry_interval=task_retry_interval,
                            task_thread_pool_size=task_thread_pool_size)

    return {
        'provider_name': 'provider',
        'provider_context': provider_context,
        'manager_ip': manager_ip,
        'ssh_user': ssh_user,
        'ssh_port': ssh_port,
        'ssh_key_path': ssh_key_path,
        'rest_port': rest_port,
        'rest_protocol': rest_protocol
    }


def teardown(name='manager',
             task_retries=5,
             task_retry_interval=30,
             task_thread_pool_size=1):
    working_env = load_env(name)
    working_env.execute('uninstall',
                        task_retries=task_retries,
                        task_retry_interval=task_retry_interval,
                        task_thread_pool_size=task_thread_pool_size)

    # deleting local environment data
    shutil.rmtree(_workdir())


def build_fabric_env(manager_ip, ssh_user, ssh_port, ssh_key_path):
    return {
        "host_string": manager_ip,
        "user": ssh_user,
        "port": ssh_port,
        "key_filename": ssh_key_path
    }


def _dump_manager_deployment(manager_node_instance):
    # explicitly write the manager node instance id to local storage
    working_env = load_env('manager')
    with working_env.storage.payload() as payload:
        payload['manager_node_instance_id'] = manager_node_instance.id

    # explicitly flush runtime properties to local storage
    manager_node_instance.update()
    return dump_manager_deployment()


def _copy_agent_key(agent_local_key_path, agent_remote_key_path,
                    fabric_env):
    if not agent_local_key_path:
        return None
    agent_local_key_path = os.path.expanduser(agent_local_key_path)
    remote_dir = os.path.dirname(agent_remote_key_path)
    with fabric.settings(**fabric_env):
        fabric.sudo('mkdir -p {0}'.format(remote_dir))
        fabric.put(agent_local_key_path, agent_remote_key_path, use_sudo=True)
    return agent_remote_key_path


def _upload_resources(manager_node,
                      fabric_env,
                      rest_client,
                      retries,
                      wait_interval):
    """Upload resources supplied in the manager blueprint. uses both fabric for
    the dsl_resources, and the upload plugins mechanism for plugin_resources.

    :param manager_node: The manager node from which to retrieve the
    properties from.
    :param fabric_env: fabric env in order to upload the dsl_resources.
    :param rest_client: the rest client to use to upload plugins
    """
    upload_resources = \
        manager_node.properties['cloudify'].get('upload_resources', {})

    params = upload_resources.get('parameters', {})
    fetch_timeout = params.get('fetch_timeout') or 30

    # Every resource is first moved/downloaded to this temp dir.
    temp_dir = tempfile.mkdtemp()
    try:
        upload_dsl_resources(
            upload_resources.get('dsl_resources', ()),
            temp_dir,
            fabric_env,
            retries,
            wait_interval,
            fetch_timeout)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def upload_dsl_resources(dsl_resources, temp_dir, fabric_env, retries,
                         wait_interval, timeout):
    """Upload dsl resources to the manager.

    :param dsl_resources: all of the dsl_resources.
    :param temp_dir: the dir to push the resources to.
    :param fabric_env: fabric env in order to upload the dsl_resources.
    :param retries: number of retries per resource download.
    :param wait_interval: interval between download retries.
    :param timeout: timeout for uploading a dsl resource.
    :return:
    """
    logger = get_logger()
    remote_plugins_folder = '/opt/manager/resources/'

    @retry(wait_fixed=wait_interval * 1000,
           stop_func=partial(_stop_retries, retries, wait_interval),
           retry_on_exception=lambda e: isinstance(e, RecoverableError))
    def upload_dsl_resource(local_path, remote_path):
        remote_dir = os.path.dirname(remote_path)
        logger.info('Uploading resources from {0} to {1}'
                    .format(local_path, remote_dir))
        fabric.run('sudo mkdir -p {0}'.format(remote_dir))

        fabric.put(local_path, remote_path, use_sudo=True)

    for dsl_resource in dsl_resources:
        source_plugin_yaml_path = dsl_resource.get('source_path')
        destination_plugin_yaml_path = dsl_resource.get('destination_path')

        if not source_plugin_yaml_path or not destination_plugin_yaml_path:
            missing_fields = []
            if source_plugin_yaml_path is None:
                missing_fields.append('source_path')
            if destination_plugin_yaml_path is None:
                missing_fields.append('destination_path')

            raise CloudifyBootstrapError(
                'The following fields are missing: {0}.'.format(
                    ','.join(missing_fields)))

        if destination_plugin_yaml_path.startswith('/'):
            destination_plugin_yaml_path = destination_plugin_yaml_path[1:]

        local_plugin_yaml_path = \
            _get_resource_into_dir(temp_dir, source_plugin_yaml_path,
                                   retries, wait_interval, timeout)

        fab_env = copy.deepcopy(fabric_env)
        fab_env['abort_exception'] = RecoverableError

        with fabric.settings(**fab_env):

            remote_plugin_yaml_file_path = \
                "{0}{1}".format(remote_plugins_folder,
                                destination_plugin_yaml_path)
            upload_dsl_resource(local_path=local_plugin_yaml_path,
                                remote_path=remote_plugin_yaml_file_path)


def _get_resource_into_dir(destination_dir, resource_source_path, retries,
                           wait_interval, timeout):
    """Copy a given path into the destination dir.

    The path could refer to
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

    @retry(wait_fixed=wait_interval * 1000,
           stop_func=partial(_stop_retries, retries, wait_interval),
           retry_on_exception=lambda e: isinstance(e, requests.Timeout))
    def download_resource(source_path, dest_path):
        try:
            resource_request = requests.get(source_path, stream=True,
                                            timeout=timeout)
            if resource_request.status_code == 200:
                with open(dest_path, 'wb') as f:
                    resource_request.raw.decode_content = True
                    shutil.copyfileobj(resource_request.raw, f)
                resource_request.close()
                logger.info('Download complete')
                return dest_path
            else:
                msg = "The resource {0} failed to download. Error {1}." \
                    .format(source_path,
                            resource_request.status_code)
                raise CloudifyBootstrapError(msg)
        except requests.RequestException as ex:
            msg = 'Failed accessing {0}: {1}'.format(source_path, str(ex))
            raise CloudifyBootstrapError(msg)

    if not parts.scheme or not parts.netloc:
        if not os.path.isabs(resource_source_path):
            resource_source_path = os.path.abspath(resource_source_path)
        logger.info('Copying from {0} to {1}'
                    .format(resource_source_path, temp_file_path))
        shutil.copyfile(resource_source_path, temp_file_path)
        logger.info('Done copying')
    else:
        logger.info('Downloading from {0} to {1}'
                    .format(resource_source_path, temp_file_path))

        return download_resource(source_path=resource_source_path,
                                 dest_path=temp_file_path)


def _stop_retries(retries, wait_interval, attempt, *args, **kwargs):
    """
    A wrapper function which enables logging for the retry mechanism.

    :param retries: Total number of retries.
    :param wait_interval: wait time between attempts.
    :param self: will be used by the retry decorator.
    :param attempt: will be used by the retry decorator.
    :param args: any args passed by the decorator.
    :param kwargs: any kwargs passed by the decorator.
    :return: True if to continue the retries, False o/w.
    """
    logger = get_logger()
    logger.info(
        'Attempt {0} out of {1} failed. Waiting for {2} seconds and trying '
        'again...'.format(attempt, retries, wait_interval))
    return retries != -1 and attempt >= retries


def generate_password(length=12):
    logger = get_logger()
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    password = ''.join(random.choice(chars) for _ in range(length))
    logger.info('Generated password: {0}'.format(password))
    return password
