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
    success = _download_package(
        PACKAGES_PATH['cloudify'],
        server_packages['components_package_url'],
        dist)
    if not success:
        lgr.error('failed to download components package. '
                  'please ensure package exists in its '
                  'configured location in the config file')
        return False

    lgr.info('downloading cloudify-core package...')
    success = _download_package(
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
        success = _download_package(
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
        success = _download_package(
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


def bootstrap_docker(cloudify_packages, docker_path=None, use_sudo=True,
                     agent_local_key_path=None, agent_remote_key_path=None,
                     manager_private_ip=None, provider_context=None):
    # CFY-1627 - plugin dependency should be removed.
    from fabric_plugin.tasks import FabricTaskError
    global lgr
    lgr = ctx.logger

    manager_ip = fabric.api.env.host_string
    lgr.info('initializing manager on the machine at {0}'.format(manager_ip))
    agent_packages = cloudify_packages.get('agents')
    try:
        distro_info = get_machine_distro()
    except FabricTaskError as e:
        err = 'failed getting platform distro. error is: {0}'.format(str(e))
        lgr.error(err)
        raise

    lgr.info('management ip is {0}'.format(manager_ip))

    if not docker_path:
        docker_path = 'docker'

    docker_installed = _is_docker_installed(docker_path, use_sudo)

    if not docker_installed:
        if 'trusty' not in distro_info:
            err = ('bootstrap using the Docker Cloudify image requires either '
                   'running on \'Ubuntu 14.04 trusty\' or having Docker '
                   'pre-installed on the remote machine.')
            lgr.error(err)
            raise NonRecoverableError(err)

        try:
            lgr.info('installing Docker on {0}.'.format(manager_ip))
            _run_command(
                'curl -sSL https://get.docker.com/ubuntu/ | sudo sh')
        except FabricTaskError:
            err = 'failed installing docker on remote host.'
            lgr.error(err)
            raise
    else:
        lgr.debug('\"docker\" is already installed.')

    if use_sudo:
        docker_exec_command = '{0} {1}'.format('sudo', docker_path)
    else:
        docker_exec_command = docker_path

    docker_image_url = cloudify_packages.get('docker', {}).get('docker_url')
    docker_data_url = \
        cloudify_packages.get('docker', {}).get('docker_data_url')
    if not docker_image_url:
        raise NonRecoverableError('no docker URL found in packages')
    if not docker_data_url:
        raise NonRecoverableError('no docker data image URL found in packages')
    try:
        lgr.info('importing cloudify-manager docker image from {0}'
                 .format(docker_image_url))
        _run_command('{0} import {1} cloudify'
                     .format(docker_exec_command, docker_image_url))
        lgr.info('importing cloudify-data docker image from {0}'
                 .format(docker_data_url))
        _run_command('{0} import {1} data'
                     .format(docker_exec_command, docker_data_url))
    except FabricTaskError as e:
        err = 'failed importing cloudify docker images from {0} {1}. reason:' \
              '{2}'.format(docker_image_url, docker_data_url, str(e))
        lgr.error(err)
        raise NonRecoverableError(err)

    agent_mount_cmd = ''
    if agent_packages:
        lgr.info('replacing existing agent packages with custom agents {0}'
                 .format(agent_packages.keys()))
        try:
            _install_agent_packages(agent_packages, distro_info)
            lgr.info('cloudify agents installation successful.')
        except FabricTaskError as e:
            err = 'failed installing custom agent packages. error is {0}' \
                  .format(str(e))
            lgr.error(err)
            raise NonRecoverableError(err)
        agent_mount_cmd = '-v /opt/manager/resources/packages:' \
                          '/opt/manager/resources/packages '

    run_cfy_management_cmd = ('{0} run -t '
                              '-v ~/:/root '
                              + agent_mount_cmd +
                              '--volumes-from data '
                              '-p 80:80 '
                              '-p 5555:5555 '
                              '-p 5672:5672 '
                              '-p 53229:53229 '
                              '-p 8100:8100 '
                              '-p 9200:9200 '
                              '-e MANAGEMENT_IP={1} '
                              '--restart=always '
                              '--name=cfy '
                              '-d cloudify:latest '
                              '/sbin/my_init') \
        .format(docker_exec_command,
                manager_private_ip or ctx.instance.host_ip)

    run_data_container_cmd = '{0} run -t -d ' \
                             '-v /etc/service/riemann ' \
                             '-v /etc/service/elasticsearch/data ' \
                             '-v /etc/service/elasticsearch/logs ' \
                             '-v /opt/influxdb/shared/data ' \
                             '-v /var/log/cloudify ' \
                             '--name data data ' \
                             'echo Data-only container' \
                             .format(docker_exec_command)

    try:
        lgr.info('starting a new cloudify data container')
        _run_command(run_data_container_cmd)
        lgr.info('starting a new cloudify mgmt docker container')
        _run_command(run_cfy_management_cmd)
    except FabricTaskError as e:
        err = 'failed running cloudify docker container. ' \
              'error is {0}'.format(str(e))
        lgr.error(err)
        raise NonRecoverableError(err)

    lgr.info('waiting for cloudify management services to start')
    started = _wait_for_management(manager_ip, timeout=120)
    if not started:
        err = 'failed waiting for cloudify management services to start.'
        lgr.info(err)
        raise NonRecoverableError(err)

    agent_remote_key_path = _copy_agent_key(agent_local_key_path,
                                            agent_remote_key_path)
    _set_manager_endpoint_data()
    _upload_provider_context(agent_remote_key_path, provider_context)
    return True


def _install_agent_packages(agent_packages, distro_info):
    # CFY-1627 - plugin dependency should be removed.
    from fabric_plugin.tasks import FabricTaskError
    agents_path = '/tmp/agents'
    try:
        _run_command('sudo mkdir -p {0}/'.format(agents_path))
    except FabricTaskError as e:
        err = 'failed creating agent packages temp dir {0}. error was {1}' \
              .format(agents_path, str(e))
        lgr.error(err)
        raise

    for agent_name, agent_url in agent_packages.items():
        try:
            if 'Ubuntu' in distro_info:
                _run_command('sudo wget -P {0}/ {1}'.format(
                    agents_path, agent_url))
            elif 'centos' in distro_info:
                _run_command('cd {0}/; sudo curl -O {1}'.format(
                    agents_path, agent_url))
        except FabricTaskError:
            err = 'failed downloading agent package from {0}'.format(agent_url)
            lgr.error(err)
            raise
    try:
        if 'Ubuntu' in distro_info:
            _run_command('sudo dpkg -i {0}/*.deb'.format(agents_path))
        elif 'centos' in distro_info:
            _run_command('sudo rpm -i {0}/*.rpm'.format(agents_path))
    except FabricTaskError as e:
        err = 'failed installing agent packages. error is: {0}'.format(str(e))
        lgr.error(err)
        raise

    return True


def _is_docker_installed(docker_path, use_sudo):
    """
    Returns true if docker run command exists
    :param docker_run_command: docker command to run
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
    # and then calling teardown. Anyway, this code will only live until we
    # implement the fuller feature of uploading manager blueprint deployments
    # to the manager.
    cloudify_configuration['manager_deployment'] = _dump_manager_deployment()

    manager_ip = fabric.api.env.host_string
    rest_client = CloudifyClient(manager_ip, REST_PORT)
    rest_client.manager.create_context('provider',
                                       provider_context)


def _run_command(command):
    return fabric.api.run(command)


def _download_package(url, path, distro):
    if 'Ubuntu' in distro:
        return _run_command('sudo wget {0} -P {1}'.format(
            path, url))
    elif 'centos' in distro:
        with cd(path):
            return _run_command('sudo curl -O {0}')


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


# temp workaround to enable teardown from different machines
def _dump_manager_deployment():
    from cloudify_cli.bootstrap.bootstrap import dump_manager_deployment
    # explicitly flush runtime properties to local storage
    ctx.instance.update()
    return dump_manager_deployment()
