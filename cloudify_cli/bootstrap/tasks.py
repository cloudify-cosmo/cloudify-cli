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


import os
import urllib
import urllib2
import json
from time import sleep, time

import fabric
import fabric.api
from fabric.context_managers import cd

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client import CloudifyClient


from cloudify_cli import utils


REST_PORT = 80

# internal runtime properties - used by the CLI to store local context
PROVIDER_RUNTIME_PROPERTY = 'provider'
MANAGER_IP_RUNTIME_PROPERTY = 'manager_ip'
MANAGER_USER_RUNTIME_PROPERTY = 'manager_user'
MANAGER_KEY_PATH_RUNTIME_PROPERTY = 'manager_key_path'

PACKAGES_PATH = {
    'cloudify': '/cloudify',
    'core': '/cloudify-core',
    'components': '/cloudify-components',
    'ui': '/cloudify-ui',
    'agents': '/cloudify-agents'
}

DISTRO_EXT = {
    'Ubuntu': '.deb',
    'centos': '.rpm',
    'xitUbuntu': '.deb'
}

lgr = None


@operation
def creation_validation(cloudify_packages, **kwargs):
    server_packages = cloudify_packages.get('server')
    docker_packages = cloudify_packages.get('docker')

    if not ((server_packages is None) ^ (docker_packages is None)):
        raise NonRecoverableError(
            'must have exactly one of "server" and "docker" properties under '
            '"cloudify_packages"')

    manager_packages = docker_packages if server_packages is None else \
        server_packages

    if not manager_packages or not isinstance(manager_packages, dict):
        raise NonRecoverableError(
            '"{0}" must be a non-empty dictionary property under '
            '"cloudify_packages"'.format(
                'docker' if server_packages is None else 'server'))

    packages_urls = manager_packages.values()
    agent_packages = cloudify_packages.get('agents', {})
    if not isinstance(agent_packages, dict):
        raise NonRecoverableError('"cloudify_packages.agents" must be a '
                                  'dictionary property')

    packages_urls.extend(agent_packages.values())
    for package_url in packages_urls:
        _validate_package_url_accessible(package_url)


def stop_manager_container(docker_path=None, use_sudo=True):
    if not docker_path:
        docker_path = 'docker'
    command = '{0} stop cfy'.format(docker_path)
    if use_sudo:
        command = 'sudo {0}'.format(command)
    _run_command(command)


def stop_docker_service(docker_service_stop_command=None, use_sudo=True):

    if not docker_service_stop_command:
        docker_service_stop_command = 'service docker stop'
    if use_sudo:
        docker_service_stop_command = 'sudo {0}'\
            .format(docker_service_stop_command)

    # this is needed so that docker will stop using the
    # /var/lib/docker directory, which might be mounted on a
    # volume.
    _run_command(docker_service_stop_command)


def bootstrap(cloudify_packages, agent_local_key_path=None,
              agent_remote_key_path=None, manager_private_ip=None,
              provider_context=None):
    global lgr
    lgr = ctx.logger

    manager_ip = fabric.api.env.host_string

    server_packages = cloudify_packages['server']
    agent_packages = cloudify_packages['agents']
    ui_included = 'ui_package_url' in server_packages

    lgr.info('initializing manager on the machine at {0}'.format(manager_ip))

    # get linux distribution to install and download
    # packages accordingly
    # dist is either the dist name or False
    dist = json.loads(get_machine_distro())[0]
    if dist:
        lgr.debug('distribution is: {0}'.format(dist))
    else:
        lgr.error('could not identify distribution {0}.'.format(dist))
        return False

    # check package compatibility with current distro
    lgr.debug('checking package-distro compatibility')
    for package, package_url in server_packages.items():
        if not _check_distro_type_match(package_url, dist):
            raise RuntimeError('wrong package type')
    for package, package_url in agent_packages.items():
        if not _check_distro_type_match(package_url, dist):
            raise RuntimeError('wrong agent package type')

    lgr.info('downloading cloudify-components package...')
    success = _download_file(
        PACKAGES_PATH['cloudify'],
        server_packages['components_package_url'],
        dist)
    if not success:
        lgr.error('failed to download components package. '
                  'please ensure package exists in its '
                  'configured location in the config file')
        return False

    lgr.info('downloading cloudify-core package...')
    success = _download_file(
        PACKAGES_PATH['cloudify'],
        server_packages['core_package_url'],
        dist)
    if not success:
        lgr.error('failed to download core package. '
                  'please ensure package exists in its '
                  'configured location in the config file')
        return False

    if ui_included:
        lgr.info('downloading cloudify-ui...')
        success = _download_file(
            PACKAGES_PATH['ui'],
            server_packages['ui_package_url'],
            dist)
        if not success:
            lgr.error('failed to download ui package. '
                      'please ensure package exists in its '
                      'configured location in the config file')
            return False
    else:
        lgr.debug('ui url not configured in provider config. '
                  'skipping ui installation.')

    for agent, agent_url in agent_packages.items():
        success = _download_file(
            PACKAGES_PATH['agents'],
            agent_packages[agent],
            dist)
        if not success:
            lgr.error('failed to download {}. '
                      'please ensure package exists in its '
                      'configured location in the config file'
                      .format(agent_url))
            return False

    lgr.info('unpacking cloudify-core packages...')
    success = _unpack(
        PACKAGES_PATH['cloudify'],
        dist)
    if not success:
        lgr.error('failed to unpack cloudify-core package.')
        return False

    lgr.info('installing cloudify on {0}...'.format(manager_ip))
    success = _run_command('sudo {0}/cloudify-components-bootstrap.sh'
                           .format(PACKAGES_PATH['components']))
    if not success:
        lgr.error('failed to install cloudify-components package.')
        return False

    # declare user to run celery. this is passed to the core package's
    # bootstrap script for installation.
    celery_user = fabric.api.env.user
    success = _run_command('sudo {0}/cloudify-core-bootstrap.sh {1} {2}'
                           .format(PACKAGES_PATH['core'],
                                   celery_user,
                                   manager_private_ip or ctx.instance.host_ip))
    if not success:
        lgr.error('failed to install cloudify-core package.')
        return False

    if ui_included:
        lgr.info('installing cloudify-ui...')
        success = _unpack(
            PACKAGES_PATH['ui'],
            dist)
        if not success:
            lgr.error('failed to install cloudify-ui.')
            return False
        lgr.info('cloudify-ui installation successful.')

    lgr.info('deploying cloudify agents')
    success = _unpack(
        PACKAGES_PATH['agents'],
        dist)
    if not success:
        lgr.error('failed to install cloudify agents.')
        return False
    lgr.info('cloudify agents installation successful.')
    lgr.info('management ip is {0}'.format(manager_ip))

    agent_remote_key_path = _copy_agent_key(agent_local_key_path,
                                            agent_remote_key_path)
    _set_manager_endpoint_data()
    _upload_provider_context(agent_remote_key_path, provider_context)
    return True


def _install_docker_if_required(docker_path, use_sudo,
                                docker_service_start_command):
    # CFY-1627 - plugin dependency should be removed.
    from fabric_plugin.tasks import FabricTaskError

    if not docker_path:
        docker_path = 'docker'
    docker_installed = _is_docker_installed(docker_path, use_sudo)
    if not docker_installed:
        try:
            distro_info = get_machine_distro()
        except FabricTaskError as e:
            err = 'failed getting platform distro. error is: {0}'\
                  .format(str(e))
            lgr.error(err)
            raise
        if 'trusty' not in distro_info:
            err = ('bootstrap using the Docker Cloudify image requires either '
                   'running on \'Ubuntu 14.04 trusty\' or having Docker '
                   'pre-installed on the remote machine.')
            lgr.error(err)
            raise NonRecoverableError(err)

        try:
            lgr.info('installing Docker')
            _run_command('curl -sSL https://get.docker.com/ubuntu/ | sudo sh')
        except FabricTaskError:
            err = 'failed installing docker on remote host.'
            lgr.error(err)
            raise
    else:
        lgr.debug('\"docker\" is already installed.')
        try:
            info_command = '{0} info'.format(docker_path)
            if use_sudo:
                info_command = 'sudo {0}'.format(info_command)
            _run_command(info_command)
        except BaseException as e:
            lgr.debug('Failed retrieving docker info: {0}'.format(str(e)))
            lgr.debug('Trying to start docker service')
            if not docker_service_start_command:
                docker_service_start_command = 'service docker start'
            if use_sudo:
                docker_service_start_command = 'sudo {0}'\
                    .format(docker_service_start_command)
            _run_command(docker_service_start_command)

    if use_sudo:
        docker_exec_command = '{0} {1}'.format('sudo', docker_path)
    else:
        docker_exec_command = docker_path
    return docker_exec_command


def _start_elasticsearch(docker_exec_command):
    elasticsearch_data_opts = '--volume=/opt/elasticsearch/data ' \
                              'docker_elasticsearch ' \
                              'echo elasticsearch data container'
    _run_docker_container(docker_exec_command, elasticsearch_data_opts,
                          'elasticsearchdata', detached=False,
                          attempts_on_corrupt=5)

    elasticsearch_opts = '--publish=9200:9200 ' \
                         '--restart="always" ' \
                         '--volume=/var/log/cloudify/elasticsearch:' \
                         '/etc/service/elasticsearch/logs ' \
                         '--volumes-from elasticsearchdata ' \
                         'docker_elasticsearch'
    _run_docker_container(docker_exec_command, elasticsearch_opts,
                          'elasticsearch', detached=True,
                          attempts_on_corrupt=5)


def _start_rabbitmq(docker_exec_command):

    rabbitmq_opts = '--publish=5672:5672 ' \
                    '--restart="always" ' \
                    '--volume=/var/log/cloudify/rabbitmq:/var/log/rabbitmq ' \
                    'docker_rabbitmq'

    _run_docker_container(docker_exec_command, rabbitmq_opts, 'rabbitmq',
                          detached=True, attempts_on_corrupt=5)


def _start_influxdb(docker_exec_command):
    influxdb_data_opts = 'docker_influxdb ' \
                         'echo influxdb data container'
    _run_docker_container(docker_exec_command, influxdb_data_opts,
                          'influxdbdata', detached=False,
                          attempts_on_corrupt=5)

    influxdb_opts = '--publish=8083:8083 ' \
                    '--publish=8086:8086 ' \
                    '--restart="always" ' \
                    '--volumes-from influxdbdata ' \
                    'docker_influxdb'
    _run_docker_container(docker_exec_command, influxdb_opts, 'influxdb',
                          detached=True, attempts_on_corrupt=5)


def _start_logstash(docker_exec_command, private_ip):
    logstash_opts = '--add-host=elasticsearch:{0} ' \
                    '--add-host=rabbitmq:{0} ' \
                    '--publish=9999:9999 ' \
                    '--restart="always" ' \
                    '--volume=/var/log/cloudify/logstash:' \
                    '/etc/service/logstash/logs ' \
                    'docker_logstash'.format(private_ip)
    _run_docker_container(docker_exec_command, logstash_opts, 'logstash',
                          detached=True, attempts_on_corrupt=5)


def _start_amqp_influx(docker_exec_command, private_ip):
    amqp_influxdb = '--add-host=influxdb:{0} ' \
                    '--add-host=rabbitmq:{0} ' \
                    '--restart="always" ' \
                    'docker_amqpinflux'.format(private_ip)
    _run_docker_container(docker_exec_command, amqp_influxdb, 'amqpinflux',
                          detached=True, attempts_on_corrupt=5)


def _start_webui(docker_exec_command, private_ip):
    webui_opts = '--publish=9001:9001 ' \
                 '--add-host=frontend:{0} ' \
                 '--add-host=influxdb:{0} ' \
                 '--restart="always" ' \
                 '--volume=/opt/cloudify-ui ' \
                 'docker_webui'.format(private_ip)
    _run_docker_container(docker_exec_command, webui_opts, 'webui',
                          detached=True, attempts_on_corrupt=5)


def _start_rest_service(docker_exec_command, private_ip):
    webui_opts = '--name="restservice" '\
                 '--hostname="restservice" '\
                 '--add-host=rabbitmq:{0} '\
                 '--add-host=elasticsearch:{0} '\
                 '--add-host=fileserver:{0} '\
                 '--publish=8100:8100 '\
                 '--restart="always" '\
                 '--volumes-from fileserver '\
                 'docker_restservice'.format(private_ip)
    _run_docker_container(docker_exec_command, webui_opts, 'restservice',
                          detached=True, attempts_on_corrupt=5)


def _start_riemann(docker_exec_command, private_ip):
    riemann_data_opts = 'docker_riemann ' \
                        'echo riemann data container'
    _run_docker_container(docker_exec_command, riemann_data_opts,
                          'riemanndata', attempts_on_corrupt=5)

    riemann_opts = '--add-host=rabbitmq:{0} ' \
                   '--add-host=frontend:{0} ' \
                   '--restart="always" ' \
                   '--volume=/var/log/cloudify/riemann:' \
                   '/etc/service/riemann/logs ' \
                   '--volumes-from riemanndata ' \
                   '--volumes-from mgmtdata ' \
                   'docker_riemann'.format(private_ip)
    _run_docker_container(docker_exec_command, riemann_opts, 'riemann',
                          detached=True, attempts_on_corrupt=5)


def _start_fileserver(docker_exec_command, cloudify_packages):
    agent_packages = cloudify_packages.get('agents')
    if agent_packages:
        # compose agent installation command.
        data_container_work_dir = '/tmp/work_dir'
        agents_dest_dir = '/opt/manager/resources/packages'
        agent_packages_install_cmd = \
            _get_install_agent_pkgs_cmd(agent_packages,
                                        data_container_work_dir,
                                        agents_dest_dir)
        agent_pkgs_mount_options = '-v {0} -w {1} ' \
            .format(agents_dest_dir,
                    data_container_work_dir)
    else:
        lgr.info('no agent packages were provided')
        agent_packages_install_cmd = 'echo no agent packages provided'
        agent_pkgs_mount_options = ''
    fileserver_data_opts = '{0} ' \
                           'docker_fileserver ' \
                           '/bin/bash -c \'{1}\'' \
                           .format(agent_pkgs_mount_options,
                                   agent_packages_install_cmd)
    _run_docker_container(docker_exec_command, fileserver_data_opts,
                          'fileserverdata', detached=False,
                          attempts_on_corrupt=5)

    fileserver_opts = '--volume=/opt/manager/resources ' \
                      '--volumes-from fileserverdata ' \
                      'docker_fileserver'
    _run_docker_container(docker_exec_command, fileserver_opts, 'fileserver',
                          detached=True, attempts_on_corrupt=5)


def _start_frontend(docker_exec_command, private_ip):
    frontend_opts = '--add-host=rabbitmq:{0} ' \
                    '--add-host=restservice:{0} ' \
                    '--add-host=webui:{0} ' \
                    '--publish=80:80 ' \
                    '--publish=53229:53229 ' \
                    '--restart="always" ' \
                    '--volume=/var/log/cloudify/rest:/var/log/cloudify ' \
                    '--volume=/var/log/cloudify/nginx:/var/log/nginx ' \
                    '--volumes-from fileserver ' \
                    '--volumes-from webui '\
                    'docker_frontend'.format(private_ip)
    _run_docker_container(docker_exec_command, frontend_opts,
                          'frontend', detached=True,
                          attempts_on_corrupt=5)


def _start_mgmt_worker(docker_exec_command, private_ip):
    # compose command to copy host VM home dir files into the data
    # containers' home dir.
    backup_vm_files_cmd, home_dir_mount_path = _get_backup_files_cmd()
    mgmt_worker_data_opts = '-v ~/:{0} ' \
                            '-v /root ' \
                            '--volume /opt/riemann ' \
                            'docker_mgmtworker ' \
                            '/bin/bash -c \'{1} && echo mgmt data container\''\
                            .format(home_dir_mount_path, backup_vm_files_cmd)
    _run_docker_container(docker_exec_command, mgmt_worker_data_opts,
                          'mgmtdata', detached=False,
                          attempts_on_corrupt=5)

    mgmt_worker_opts = '--add-host=rabbitmq:{0} ' \
                       '--add-host=frontend:{0} ' \
                       '--add-host=fileserver:{0} ' \
                       '--env="MANAGEMENT_IP={0}" ' \
                       '--volumes-from mgmtdata ' \
                       '--restart="always" ' \
                       '--volume=/var/log/cloudify/mgmtworker:' \
                       '/opt/mgmtworker/logs ' \
                       'docker_mgmtworker'.format(private_ip)
    _run_docker_container(docker_exec_command, mgmt_worker_opts, 'mgmtworker',
                          detached=True, attempts_on_corrupt=5)


def _setup_logs_dir(use_sudo, logs_folder_name):
    if use_sudo:
        sudo = 'sudo'
    else:
        sudo = ''

    setup_logs_dir_cmd = '{0} mkdir -p /var/log/cloudify/{1} ' \
                         '&& {0} chmod -R 777 /var/log/cloudify/{1}'\
                         .format(sudo, logs_folder_name)
    _run_command(setup_logs_dir_cmd)


def bootstrap_docker(cloudify_packages, docker_path=None, use_sudo=True,
                     agent_local_key_path=None, agent_remote_key_path=None,
                     manager_private_ip=None, provider_context=None,
                     docker_service_start_command=None):
    if 'containers_started' in ctx.instance.runtime_properties:
        try:
            recover_docker(docker_path, use_sudo, docker_service_start_command)
            # the runtime property specifying the manager openstack instance id
            # has changed, so we need to update the manager deployment in the
            # provider context.
            _update_manager_deployment()
        except Exception:
            # recovery failed, however runtime properties may have still
            # changed. update the local manager deployment only
            _update_manager_deployment(local_only=True)
            raise

        return
    # CFY-1627 - plugin dependency should be removed.
    from fabric_plugin.tasks import FabricTaskError
    global lgr
    lgr = ctx.logger

    manager_ip = fabric.api.env.host_string
    private_ip = manager_private_ip or ctx.instance.host_ip
    lgr.info('initializing manager on the machine at {0}'.format(manager_ip))
    docker_exec_command = _install_docker_if_required(
        docker_path,
        use_sudo,
        docker_service_start_command)

    docker_images_url = cloudify_packages.get('docker', {}).get('docker_url')
    if not docker_images_url:
        raise NonRecoverableError('no docker URL found in packages')

    distro_info = get_machine_distro()
    tmp_image_location = '/tmp/cloudify_images.tar'
    try:
        lgr.info('downloading docker images from {0} to {1}'
                 .format(docker_images_url, tmp_image_location))
        _download_file(docker_images_url, tmp_image_location,
                       distro_info, use_sudo)
    except FabricTaskError as e:
        err = 'failed downloading cloudify docker images from {0}. reason:{1}'\
              .format(docker_images_url, str(e))
        lgr.error(err)
        raise NonRecoverableError(err)
    try:
        lgr.info('loading cloudify images from {0}'.format(tmp_image_location))
        _run_command('{0} load --input {1}'
                     .format(docker_exec_command, tmp_image_location))
    except FabricTaskError as e:
        err = 'failed loading cloudify docker images from {0}. reason:{1}' \
              .format(tmp_image_location, str(e))
        lgr.error(err)
        raise NonRecoverableError(err)

    # copy agent key to host VM. This file, along with all files on the
    # host VMs home-dir will be stored in the mgmt_worker_data container
    agent_remote_key_path = _copy_agent_key(agent_local_key_path,
                                            agent_remote_key_path)
    lgr.info('starting cloudify management services')
    try:
        _setup_logs_dir(use_sudo, 'fileserver')
        _start_fileserver(docker_exec_command, cloudify_packages)

        _setup_logs_dir(use_sudo, 'restservice')
        _start_rest_service(docker_exec_command, private_ip)

        _setup_logs_dir(use_sudo, 'webui')
        _start_webui(docker_exec_command, private_ip)

        _setup_logs_dir(use_sudo, 'mgmtworker')
        _start_mgmt_worker(docker_exec_command, private_ip)

        _setup_logs_dir(use_sudo, 'elasticsearch')
        _start_elasticsearch(docker_exec_command)

        _setup_logs_dir(use_sudo, 'rabbitmq')
        _start_rabbitmq(docker_exec_command)

        _setup_logs_dir(use_sudo, 'influxdb')
        _start_influxdb(docker_exec_command)

        _setup_logs_dir(use_sudo, 'logstash')
        _start_logstash(docker_exec_command, private_ip)

        _setup_logs_dir(use_sudo, 'amqpinflux')
        _start_amqp_influx(docker_exec_command, private_ip)

        _setup_logs_dir(use_sudo, 'frontend')
        _start_frontend(docker_exec_command, private_ip)

        _setup_logs_dir(use_sudo, 'riemann')
        _start_riemann(docker_exec_command, private_ip)
    except FabricTaskError as e:
        err = 'failed running cloudify service containers. ' \
              'error is {0}'.format(str(e))
        lgr.error(err)
        raise NonRecoverableError(err)

    lgr.info('waiting for cloudify management services to start')
    started = _wait_for_management(manager_ip, timeout=180)
    ctx.instance.runtime_properties['containers_started'] = 'True'
    if not started:
        err = 'failed waiting for cloudify management services to start.'
        lgr.info(err)
        raise NonRecoverableError(err)

    _set_manager_endpoint_data()
    _upload_provider_context(agent_remote_key_path, provider_context)
    return True


def recover_docker(docker_path=None, use_sudo=True,
                   docker_service_start_command=None):
    global lgr
    lgr = ctx.logger

    manager_ip = fabric.api.env.host_string
    lgr.info('initializing manager on the machine at {0}'.format(manager_ip))
    _install_docker_if_required(docker_path, use_sudo,
                                docker_service_start_command)

    lgr.info('waiting for cloudify management services to restart')
    started = _wait_for_management(manager_ip, timeout=180)
    _recover_deployments(docker_path, use_sudo)
    if not started:
        err = 'failed waiting for cloudify management services to restart.'
        lgr.info(err)
        raise NonRecoverableError(err)


def _recover_deployments(docker_path=None, use_sudo=True):

    ctx.logger.info('Recovering deployments...')
    script_relpath = ctx.instance.runtime_properties.get(
        'recovery_script_relpath')
    if not script_relpath:
        raise NonRecoverableError('Cannot recover deployments. No recovery '
                                  'script specified.')
    script = ctx.download_resource(
        script_relpath)
    fabric.api.put(script, '~/recover_deployments.sh')
    _run_command('chmod +x ~/recover_deployments.sh')
    _run_command_in_cfy('/tmp/home/recover_deployments.sh',
                        docker_path=docker_path,
                        use_sudo=use_sudo)


def _get_backup_files_cmd():
    container_tmp_homedir_path = '/tmp/home'
    backup_homedir_cmd = 'cp -rf {0}/. /root' \
                         .format(container_tmp_homedir_path)
    return backup_homedir_cmd, container_tmp_homedir_path


def _get_install_agent_pkgs_cmd(agent_packages,
                                agents_pkg_path,
                                agents_dest_dir):
    install_agents_cmd = ''
    download_agents_cmd = 'mkdir -p {0} && cd {0} {1}'.format(agents_pkg_path,
                                                              ' && ')
    for agent_name, agent_url in agent_packages.items():
        download_agents_cmd += 'curl -O {0}{1} ' \
                               .format(agent_url, ' && ')

    install_agents_cmd += 'rm -rf {0}/* && dpkg -i {1}/*.deb' \
                          .format(agents_dest_dir,
                                  agents_pkg_path)

    return '{0} {1}'.format(download_agents_cmd, install_agents_cmd)


def _is_docker_installed(docker_path, use_sudo):
    """
    Returns true if docker run command exists
    :param docker_path: the docker path
    :param use_sudo: use sudo to run docker
    :return: True if docker run command exists, False otherwise
    """
    # CFY-1627 - plugin dependency should be removed.
    from fabric_plugin.tasks import FabricTaskError
    try:
        if use_sudo:
            out = fabric.api.run('sudo which {0}'.format(docker_path))
        else:
            out = fabric.api.run('which {0}'.format(docker_path))
        if not out:
            return False
        return True
    except FabricTaskError:
        return False


def _wait_for_management(ip, timeout, port=80):
    """ Wait for url to become available
        :param ip: the manager IP
        :param timeout: in seconds
        :param port: port used by the rest service.
        :return: True of False
    """
    validation_url = 'http://{0}:{1}/blueprints'.format(ip, port)

    end = time() + timeout

    while end - time() >= 0:
        try:
            status = urllib.urlopen(validation_url).getcode()
            if status == 200:
                return True

        except IOError as e:
            lgr.debug('error waiting for {0}. reason: {1}'
                      .format(validation_url, e.message))
        sleep(5)

    return False


def _set_manager_endpoint_data():
    ctx.instance.runtime_properties[MANAGER_IP_RUNTIME_PROPERTY] = \
        fabric.api.env.host_string
    ctx.instance.runtime_properties[MANAGER_USER_RUNTIME_PROPERTY] = \
        fabric.api.env.user
    ctx.instance.runtime_properties[MANAGER_KEY_PATH_RUNTIME_PROPERTY] = \
        fabric.api.env.key_filename


def _copy_agent_key(agent_local_key_path=None,
                    agent_remote_key_path=None):
    ctx.logger.info('Copying agent key to management machine')
    if not agent_local_key_path:
        return
    agent_remote_key_path = agent_remote_key_path or '~/.ssh/agent_key.pem'
    agent_local_key_path = os.path.expanduser(agent_local_key_path)
    fabric.api.put(agent_local_key_path, agent_remote_key_path)
    return agent_remote_key_path


def _update_manager_deployment(local_only=False):

    # get the current provider from the runtime property set on bootstrap
    provider_context = ctx.instance.runtime_properties[
        PROVIDER_RUNTIME_PROPERTY]

    # construct new manager deployment
    provider_context['cloudify'][
        'manager_deployment'] = _dump_manager_deployment()

    # update locally
    ctx.instance.runtime_properties[
        PROVIDER_RUNTIME_PROPERTY] = provider_context
    with utils.update_wd_settings() as wd_settings:
        wd_settings.set_provider_context(provider_context)

    if not local_only:
        # update on server
        rest_client = utils.get_rest_client()
        rest_client.manager.update_context('provider', provider_context)


def _upload_provider_context(remote_agents_private_key_path,
                             provider_context=None):
    provider_context = provider_context or dict()
    cloudify_configuration = ctx.node.properties['cloudify']
    cloudify_configuration['cloudify_agent']['agent_key_path'] = \
        remote_agents_private_key_path
    provider_context['cloudify'] = cloudify_configuration
    ctx.instance.runtime_properties[PROVIDER_RUNTIME_PROPERTY] = \
        provider_context

    # 'manager_deployment' is used when running 'cfy use ...'
    # and then calling teardown or recover. Anyway, this code will only live
    # until we implement the fuller feature of uploading manager blueprint
    # deployments to the manager.
    cloudify_configuration['manager_deployment'] = _dump_manager_deployment()

    manager_ip = fabric.api.env.host_string
    rest_client = CloudifyClient(manager_ip, REST_PORT)
    rest_client.manager.create_context('provider',
                                       provider_context)


def _run_command(command):
    return fabric.api.run(command)


def _run_command_in_cfy(command, docker_path=None, use_sudo=True):
    if not docker_path:
        docker_path = 'docker'
    full_command = '{0} exec cfy {1}'.format(
        docker_path, command)
    if use_sudo:
        full_command = 'sudo {0}'.format(full_command)
    _run_command(full_command)


def _container_exists(docker_exec_command, container_name):
    # CFY-1627 - plugin dependency should be removed.
    from fabric_plugin.tasks import FabricTaskError
    try:
        inspect_command = '{0} inspect {1}'.format(docker_exec_command,
                                                   container_name)
        _run_command(inspect_command)
        return True
    except FabricTaskError:
        return False


def _run_docker_container(docker_exec_command, container_options,
                          container_name, detached=False,
                          attempts_on_corrupt=1):
    # CFY-1627 - plugin dependency should be removed.
    from fabric_plugin.tasks import FabricTaskError

    if _container_exists(docker_exec_command, container_name):
        raise NonRecoverableError('container with name {0} already exists'
                                  .format(container_name))

    run_cmd = '{0} run --name {1} --hostname={1} --detach={2} {3}' \
        .format(docker_exec_command, container_name,
                detached, container_options)
    for i in range(0, attempts_on_corrupt):
        try:
            lgr.debug('starting docker container {0}'.format(container_name))
            return _run_command(run_cmd)
        except FabricTaskError:
            lgr.debug('container execution failed on attempt {0}/{1}'
                      .format(i + 1, attempts_on_corrupt))
            container_exists = _container_exists(docker_exec_command,
                                                 container_name)
            if container_exists:
                lgr.debug('container {0} started in a corrupt state. '
                          'removing container.'.format(container_name))
                rm_container_cmd = '{0} rm -f {1}'.format(docker_exec_command,
                                                          container_name)
                _run_command(rm_container_cmd)
            if not container_exists or i + 1 == attempts_on_corrupt:
                lgr.error('failed executing command: {0}'.format(run_cmd))
                raise
            sleep(2)


def _download_file(url, path, distro, use_sudo=True):
    if use_sudo:
        sudo = 'sudo'
    else:
        sudo = ''

    if 'Ubuntu' in distro:
        # todo: remove silent -q0- wget.
        return _run_command('{0} wget -qO- -O {1} {2}'.format(sudo, path, url))
    elif 'centos' in distro:
        # todo(adaml): fix this.
        with cd(path):
            return _run_command('{0} curl -O {1}').format(sudo, url)


def _unpack(path, distro):
    if 'Ubuntu' in distro:
        return _run_command('sudo dpkg -i {0}/*.deb'.format(path))
    elif 'centos' in distro:
        return _run_command('sudo rpm -i {0}/*.rpm'.format(path))


def _check_distro_type_match(url, distro):
    lgr.debug('checking distro-type match for url: {}'.format(url))
    ext = _get_ext(url)
    if not DISTRO_EXT[distro] == ext:
        lgr.error('wrong package type: '
                  '{} required. {} supplied. in url: {}'
                  .format(DISTRO_EXT[distro], ext, url))
        return False
    return True


def get_machine_distro():
    return _run_command('python -c "import platform, json, sys; '
                        'sys.stdout.write(\'{0}\\n\''
                        '.format(json.dumps(platform.dist())))"')


def _get_ext(url):
    lgr.debug('extracting file extension from url')
    filename = urllib2.unquote(url).decode('utf8').split('/')[-1]
    return os.path.splitext(filename)[1]


def _validate_package_url_accessible(package_url):
    ctx.logger.debug('checking whether url {0} is accessible'.format(
        package_url))
    status = urllib.urlopen(package_url).getcode()
    if not status == 200:
        err = ('url {0} is not accessible'.format(package_url))
        ctx.logger.error('VALIDATION ERROR: ' + err)
        raise NonRecoverableError(err)
    ctx.logger.debug('OK: url {0} is accessible'.format(package_url))


# temp workaround to enable teardown and recovery from different machines
def _dump_manager_deployment():
    from cloudify_cli.bootstrap.bootstrap import dump_manager_deployment
    from cloudify_cli.bootstrap.bootstrap import load_env

    # explicitly write the manager node instance id to local storage
    env = load_env('manager')
    with env.storage.payload() as payload:
        payload['manager_node_instance_id'] = ctx.instance.id

    # explicitly flush runtime properties to local storage
    ctx.instance.update()
    return dump_manager_deployment()
