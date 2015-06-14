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
import json
import pkgutil
import tarfile
import tempfile
from time import sleep, time
from StringIO import StringIO

import jinja2
import fabric
import fabric.api

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify_cli import utils
from cloudify_cli import constants

# internal runtime properties - used by the CLI to store local context
PROVIDER_RUNTIME_PROPERTY = 'provider'
MANAGER_IP_RUNTIME_PROPERTY = 'manager_ip'
MANAGER_USER_RUNTIME_PROPERTY = 'manager_user'
MANAGER_KEY_PATH_RUNTIME_PROPERTY = 'manager_key_path'
DEFAULT_REMOTE_AGENT_KEY_PATH = '~/.ssh/agent_key.pem'
REST_PORT = 'rest_port'

HOST_CLOUDIFY_HOME_DIR = '~/cloudify'
HOST_SSL_CERTIFICATE_PATH = '~/cloudify/server.crt'
HOST_SSL_PRIVATE_KEY_PATH = '~/cloudify/server.key'

DEFAULT_SECURITY_LOG_FOLDER = '/var/log/cloudify'
DEFAULT_SECURITY_LOG_FILE = DEFAULT_SECURITY_LOG_FOLDER \
    + "/rest-security-audit.log"
DEFAULT_SECURITY_LOG_LEVEL = 'INFO'
DEFAULT_SECURITY_LOG_FILE_SIZE_MB = 100
DEFAULT_SECURITY_LOG_FILES_BACKUP_COUNT = 20
DEFAULT_SECURITY_MODE = False

lgr = None


@operation
def creation_validation(cloudify_packages, **kwargs):
    if not isinstance(cloudify_packages, dict):
        raise NonRecoverableError('"cloudify_packages" must be a '
                                  'dictionary property')
    docker_packages = cloudify_packages.get('docker')

    if not docker_packages or not isinstance(docker_packages, dict):
        raise NonRecoverableError(
            '"docker" must be a non-empty dictionary property under '
            '"cloudify_packages"')

    packages_urls = docker_packages.values()
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


def _install_docker_if_required(docker_path, use_sudo,
                                docker_service_start_command):
    # CFY-1627 - plugin dependency should be removed.
    from fabric_plugin.tasks import FabricTaskError

    sudo = 'sudo' if use_sudo else ''
    if not docker_path:
        docker_path = 'docker'
    docker_installed = _is_installed(docker_path, use_sudo)
    if not docker_installed:
        try:
            distro_info = get_machine_distro()
        except FabricTaskError as e:
            err = 'failed getting platform distro. error is: {0}'\
                  .format(str(e))
            lgr.error(err)
            raise
        if 'ubuntu' not in distro_info \
                and 'centos' not in distro_info \
                    and 'redhat' not in distro_info:
            err = ('bootstrapping requires either having Docker pre-installed '
                   'on the host or using the following OS distributions: '
                   'Ubuntu 14.04 trusty, Centos 6.5/7.x, RHEL 6.5/7.x')
            lgr.error(err)
            raise NonRecoverableError(err)
        lgr.info('installing Docker')
        try:
            # https://github.com/docker/docker/issues/11910
            if 'Maipo' in distro_info:
                # RHEL 7.x
                _run_command('{0} yum-config-manager --enable '
                             'rhui-REGION-rhel-server-extras'.format(sudo))
                _run_command('{0} yum install -y docker'.format(sudo))
            elif 'Santiago' in distro_info or 'Final' in distro_info:
                _run_command('{0} curl -o /tmp/epel-release-6-8.noarch.rpm'
                             ' http://mirror.nonstop.co.il/epel/6/i386/'
                             'epel-release-6-8.noarch.rpm'.format(sudo))
                _run_command('{0} rpm -Uvh /tmp/epel-release-6-8.noarch'
                             '.rpm'.format(sudo))
                _run_command('{0} yum install -y docker-io'.format(sudo))
                _run_command('{0} curl -o /usr/bin/docker https://get.docker'
                             '.com/builds/Linux/x86_64/docker-latest'
                             .format(sudo))
            else:
                # Centos 7.x, Ubuntu 14.04
                _run_command('curl -sSL https://get.docker.com/ | {0} sh'
                             .format(sudo))

            if 'Santiago' in distro_info or 'Final' in distro_info:
                # required on Centos6.5 in order to be able to run pty=False
                _run_command('{0} sed -i "s/^.*requiretty/#Defaults '
                             'requiretty/" /etc/sudoers'.format(sudo))
                _run_command('{0} service docker restart'.format(sudo),
                             pty=False)
            else:
                _run_command('{0} service docker restart'.format(sudo))

            # selinux security
            if 'Maipo' in distro_info or 'Core' in distro_info:
                _add_selinux_rule(use_sudo)

        except FabricTaskError as e:
            err = 'failed installing docker on remote host. reason: {0}'\
                  .format(e.message)
            lgr.error(err)
            raise
    else:
        lgr.debug('\"docker\" is already installed.')
        try:
            info_command = '{0} {1} info'.format(sudo, docker_path)
            _run_command(info_command)
        except BaseException as e:
            lgr.debug('Failed retrieving docker info: {0}'.format(str(e)))
            lgr.debug('Trying to start docker service')
            if not docker_service_start_command:
                docker_service_start_command = '{0} service docker start'\
                                               .format(sudo)
            _run_command(docker_service_start_command)

    if use_sudo:
        docker_exec_command = '{0} {1}'.format('sudo', docker_path)
    else:
        docker_exec_command = docker_path
    return docker_exec_command


def is_selinux(use_sudo):
    return _is_installed('sestatus', use_sudo)


# TODO(adaml): Not required in RHEL 6.5
def _add_selinux_rule(use_sudo):
    if (is_selinux(use_sudo)):
        lgr.info('running on an SELINUX distribution')
        selinux_status = \
            _run_command('sestatus |grep \'SELinux status\'| '
                         'awk \'{print $3}\'')

        if selinux_status == 'enabled':
            lgr.info('changing security context of user home dir')
            _run_command('chcon -Rt svirt_sandbox_file_t ~/')


def _handle_ssl_configuration(ssl_configuration):
    enabled = ssl_configuration.get(
        constants.SSL_ENABLED_PROPERTY_NAME, False)
    if enabled is True:
        # get cert and key file paths
        cert_path = ssl_configuration.get(
            constants.SSL_CERTIFICATE_PATH_PROPERTY_NAME)
        if not cert_path:
            raise NonRecoverableError(
                'SSL is enabled => certificate path must be provided')
        cert_path = os.path.expanduser(cert_path)
        if not os.path.exists(cert_path):
            raise NonRecoverableError(
                'The certificate path [{0}] does not exist'
                .format(cert_path))
        key_path = ssl_configuration.get(
            constants.SSL_PRIVATE_KEY_PROPERTY_NAME)
        if not key_path:
            raise NonRecoverableError(
                'SSL is enabled => private key path must be provided')
        key_path = os.path.expanduser(key_path)
        if not os.path.exists(key_path):
            raise NonRecoverableError(
                'The private key path [{0}] does not exist'
                .format(key_path))
        os.environ[constants.CLOUDIFY_SSL_CERT] = cert_path
        rest_port = constants.SECURED_REST_PORT

        # copy cert and key files to the host,
        _copy_ssl_files(local_cert_path=cert_path,
                        remote_cert_path=HOST_SSL_CERTIFICATE_PATH,
                        local_key_path=key_path,
                        remote_key_path=HOST_SSL_PRIVATE_KEY_PATH)
    else:
        rest_port = constants.DEFAULT_REST_PORT

    ctx.instance.runtime_properties[REST_PORT] = rest_port


def bootstrap_docker(cloudify_packages, docker_path=None, use_sudo=True,
                     agent_local_key_path=None, agent_remote_key_path=None,
                     manager_private_ip=None, provider_context=None,
                     docker_service_start_command=None, privileged=False):
    if agent_remote_key_path is None:
        agent_remote_key_path = DEFAULT_REMOTE_AGENT_KEY_PATH

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
    lgr.info('initializing manager on the machine at {0}'.format(manager_ip))

    def post_bootstrap_actions(wait_for_services_timeout=180):
        port = ctx.instance.runtime_properties[REST_PORT]
        lgr.info(
            'waiting for cloudify management services to start on port {0}'
            .format(port))
        started = _wait_for_management(
            ip=manager_ip, timeout=wait_for_services_timeout, port=port)
        if not started:
            err = 'failed waiting for cloudify management services to start.'
            lgr.info(err)
            raise NonRecoverableError(err)
        _set_manager_endpoint_data()

        ctx.instance.runtime_properties['containers_started'] = 'True'
        try:
            _upload_provider_context(agent_remote_key_path, provider_context)
        except:
            del ctx.instance.runtime_properties['containers_started']
            raise
        return True

    if ctx.operation.retry_number > 0:
        return post_bootstrap_actions(wait_for_services_timeout=15)

    _run_command('mkdir -p {0}'.format(HOST_CLOUDIFY_HOME_DIR))
    docker_exec_command = _install_docker_if_required(
        docker_path,
        use_sudo,
        docker_service_start_command)

    data_container_name = 'data'
    cfy_container_name = 'cfy'
    if _container_exists(docker_exec_command, data_container_name) or \
            _container_exists(docker_exec_command, cfy_container_name):
        err = 'a container instance with name {0}/{1} already exists.'\
              .format(data_container_name, cfy_container_name)
        raise NonRecoverableError(err)

    docker_image_url = cloudify_packages.get('docker', {}).get('docker_url')
    if not docker_image_url:
        raise NonRecoverableError('no docker URL found in packages')
    try:
        lgr.info('importing cloudify-manager docker image from {0}'
                 .format(docker_image_url))
        _run_command('{0} import {1} cloudify'
                     .format(docker_exec_command, docker_image_url))
    except FabricTaskError as e:
        err = 'failed importing cloudify docker image from {0}. reason:{1}' \
              .format(docker_image_url, str(e))
        lgr.error(err)
        raise NonRecoverableError(err)

    cloudify_config = ctx.node.properties['cloudify']
    security_config = cloudify_config.get('security', {})
    security_config_path = _handle_security_configuration(security_config)

    ssl_configuration = security_config.get('ssl', {})
    _handle_ssl_configuration(ssl_configuration)

    rest_port = ctx.instance.runtime_properties[REST_PORT]
    lgr.info('exposing port {0}'.format(rest_port))
    cfy_management_options = ('-t '
                              '--volumes-from data '
                              '--privileged={0} '
                              '-p {1}:{1} '
                              '-p 5555:5555 '
                              '-p 5672:5672 '
                              '-p 53229:53229 '
                              '-p 8100:8100 '
                              '-p 8101:8101 '
                              '-p 9200:9200 '
                              '-p 8086:8086 '
                              '-e MANAGEMENT_IP={2} '
                              '-e MANAGER_REST_SECURITY_CONFIG_PATH={3} '
                              '--restart=always '
                              '-d '
                              'cloudify '
                              '/sbin/my_init'
                              .format(privileged,
                                      rest_port,
                                      manager_private_ip or
                                      ctx.instance.host_ip,
                                      security_config_path))

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

    # command to copy host VM home dir files into the data container's home.
    backup_vm_files_cmd, home_dir_mount_path = _get_backup_files_cmd()
    # copy agent to host VM. the data container will mount the host VM's
    # home-dir so that all files will be backed up inside the data container.
    _copy_agent_key(agent_local_key_path, agent_remote_key_path)

    install_plugins_cmd = _handle_plugins_and_create_install_cmd(
        cloudify_config.get('plugins', {}))

    data_container_start_cmd = '{0} && {1} && {2} && echo Data-only container'\
                               .format(agent_packages_install_cmd,
                                       backup_vm_files_cmd,
                                       install_plugins_cmd)
    data_container_options = ('-t '
                              '{0} '
                              '-v ~/:{1} '
                              '-v /root '
                              '--privileged={2} '
                              '-v /etc/init.d '
                              '-v /etc/default '
                              '-v /opt/manager/resources '
                              '-v /opt/manager/env '
                              '-v /etc/service/riemann '
                              '-v /etc/service/elasticsearch/data '
                              '-v /etc/service/elasticsearch/logs '
                              '-v /opt/influxdb/shared/data '
                              '-v /var/log/cloudify '
                              'cloudify sh -c \'{3}\''
                              .format(agent_pkgs_mount_options,
                                      home_dir_mount_path,
                                      privileged,
                                      data_container_start_cmd))

    try:
        lgr.info('starting a new cloudify data container')
        _run_docker_container(docker_exec_command, data_container_options,
                              data_container_name)
        lgr.info('starting a new cloudify mgmt docker services container')
        _run_docker_container(docker_exec_command, cfy_management_options,
                              cfy_container_name, attempts_on_corrupt=5)
    except FabricTaskError as e:
        err = 'failed running cloudify docker container. ' \
              'error is {0}'.format(str(e))
        lgr.error(err)
        raise NonRecoverableError(err)

    return post_bootstrap_actions()


def recover_docker(docker_path=None, use_sudo=True,
                   docker_service_start_command=None):
    global lgr
    lgr = ctx.logger

    manager_ip = fabric.api.env.host_string
    lgr.info('initializing manager on the machine at {0}'.format(manager_ip))
    _install_docker_if_required(docker_path, use_sudo,
                                docker_service_start_command)

    lgr.info('waiting for cloudify management services to restart')
    port = ctx.instance.runtime_properties[REST_PORT]
    started = _wait_for_management(manager_ip, timeout=180, port=port)
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
    download_agents_cmd = ''
    install_agents_cmd = ''
    for agent_name, agent_url in agent_packages.items():
        download_agents_cmd += 'curl -O {0}{1} ' \
                               .format(agent_url, ' && ')

    install_agents_cmd += 'rm -rf {0}/* && dpkg -i {1}/*.deb' \
                          .format(agents_dest_dir,
                                  agents_pkg_path)

    return '{0} {1}'.format(download_agents_cmd, install_agents_cmd)


def _handle_plugins_and_create_install_cmd(plugins):
    # no plugins configured, run a stub 'true' command
    if not plugins:
        return 'true'

    cloudify_plugins = 'cloudify/plugins'
    install_plugins = 'install_plugins.sh'

    # create location to place tar-gzipped plugins in
    _run_command('mkdir -p ~/{0}'.format(cloudify_plugins))

    # for each plugin tha is included in the blueprint, tar-gzip it
    # and place it in the plugins dir on the host
    for name, plugin in plugins.items():
        source = plugin['source']
        if source.split('://')[0] in ['http', 'https']:
            continue

        # temporary workaround to resolve absolute file path
        # to installed plugin using internal local workflows storage
        # information
        plugin_path = os.path.join(ctx._endpoint.storage.resources_root,
                                   source)

        with tempfile.TemporaryFile() as fileobj:
            with tarfile.open(fileobj=fileobj, mode='w:gz') as tar:
                tar.add(plugin_path, arcname=name)
            fileobj.seek(0)
            tar_remote_path = '{0}/{1}.tar.gz'.format(cloudify_plugins, name)
            fabric.api.put(fileobj, '~/{0}'.format(tar_remote_path))
            plugin['source'] = 'file:///root/{0}'.format(tar_remote_path)

    # render script template and copy it to host's home dir
    script_template = pkgutil.get_data('cloudify_cli.bootstrap.resources',
                                       'install_plugins.sh.template')
    script = jinja2.Template(script_template).render(plugins=plugins)
    fabric.api.put(StringIO(script), '~/{0}'.format(install_plugins))
    _run_command('chmod +x ~/{0}'.format(install_plugins))
    # path to script on container after host's home has been copied to
    # container's home
    return '/root/{0}'.format(install_plugins)


def _is_installed(package_name, use_sudo):
    """
    Returns true if docker run command exists
    :param package_name: the name of the package
    :param use_sudo: use sudo to run docker
    :return: True if docker run command exists, False otherwise
    """
    # CFY-1627 - plugin dependency should be removed.
    from fabric_plugin.tasks import FabricTaskError
    try:
        if use_sudo:
            out = fabric.api.run('sudo which {0}'.format(package_name))
        else:
            out = fabric.api.run('which {0}'.format(package_name))
        if not out:
            return False
        return True
    except FabricTaskError:
        return False


def _wait_for_management(ip, timeout, port=constants.DEFAULT_REST_PORT):
    """ Wait for url to become available
        :param ip: the manager IP
        :param timeout: in seconds
        :param port: port used by the rest service.
        :return: True of False
    """
    protocol = 'http' if port == constants.DEFAULT_REST_PORT else 'https'
    validation_url = '{0}://{1}:{2}/version'.format(protocol, ip, port)
    lgr.info('waiting for url {0} to become available'.format(validation_url))

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


def _handle_security_configuration(blueprint_security_config):
    remote_security_config_path = '~/rest-security-config.json'
    container_security_config_path = '/root/rest-security-config.json'

    secured_server = blueprint_security_config.get(
        'enabled', DEFAULT_SECURITY_MODE)
    auth_token_generator = blueprint_security_config.get(
        'auth_token_generator', {})
    securest_userstore_driver = blueprint_security_config.get(
        'userstore_driver', {})
    securest_authentication_providers = blueprint_security_config.get(
        'authentication_providers', [])
    securest_log_level = blueprint_security_config.get(
        'audit_log_level', DEFAULT_SECURITY_LOG_LEVEL)
    securest_log_file = blueprint_security_config.get(
        'audit_log_file', DEFAULT_SECURITY_LOG_FILE)
    securest_log_file_size_MB = blueprint_security_config.get(
        'audit_log_file_size_MB', DEFAULT_SECURITY_LOG_FILE_SIZE_MB)
    securest_log_files_backup_count = blueprint_security_config.get(
        'audit_log_files_backup_count',
        DEFAULT_SECURITY_LOG_FILES_BACKUP_COUNT)

    security_config = dict(
        secured_server=secured_server,
        auth_token_generator=auth_token_generator,
        securest_userstore_driver=securest_userstore_driver,
        securest_authentication_providers=securest_authentication_providers,
        securest_log_level=securest_log_level,
        securest_log_file=securest_log_file,
        securest_log_file_size_MB=securest_log_file_size_MB,
        securest_log_files_backup_count=securest_log_files_backup_count
    )
    security_config_file_obj = StringIO()
    json.dump(security_config, security_config_file_obj)
    fabric.api.put(security_config_file_obj, remote_security_config_path)
    return container_security_config_path


def _copy_ssl_files(
        local_cert_path, remote_cert_path, local_key_path, remote_key_path):
    ctx.logger.info(
        'Copying SSL certificate to management machine: {0} -> {1}'.format(
            local_cert_path, remote_cert_path))
    fabric.api.put(local_cert_path, remote_cert_path)

    ctx.logger.info(
        'Copying SSL key to management machine: {0} -> {1}'.format(
            local_key_path, remote_key_path))
    fabric.api.put(local_key_path, remote_key_path)


def _copy_agent_key(agent_local_key_path, agent_remote_key_path):
    if not agent_local_key_path:
        return
    agent_local_key_path = os.path.expanduser(agent_local_key_path)
    ctx.logger.info(
        'Copying agent key to management machine: {0} -> {1}'.format(
            agent_local_key_path, agent_remote_key_path))
    fabric.api.put(agent_local_key_path, agent_remote_key_path)


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
    ctx.logger.info('updating provider context on management server...')
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

    remote_provider_context_file = '~/provider-context.json'
    container_provider_context_file = '/tmp/home/provider-context.json'
    provider_context_json_file = StringIO()
    full_provider_context = {
        'name': 'provider',
        'context': provider_context
    }
    json.dump(full_provider_context, provider_context_json_file)

    # placing provider context file in the manager's host
    fabric.api.put(provider_context_json_file,
                   remote_provider_context_file)

    upload_provider_context_cmd = \
        'curl --fail -XPOST localhost:8101/provider/context -H ' \
        '"Content-Type: application/json" -d @{0}'.format(
            container_provider_context_file)

    # uploading the provider context to the REST service
    _run_command_in_cfy(upload_provider_context_cmd, terminal=True)


def _run_command(command, shell_escape=None, pty=True):
    return fabric.api.run(command, shell_escape=shell_escape, pty=pty)


def _run_command_in_cfy(command, docker_path=None, use_sudo=True,
                        terminal=False):
    if not docker_path:
        docker_path = 'docker'
    exec_command = 'exec -t' if terminal else 'exec'
    full_command = '{0} {1} cfy {2}'.format(
        docker_path, exec_command, command)
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
                          container_name, attempts_on_corrupt=1):
    # CFY-1627 - plugin dependency should be removed.
    from fabric_plugin.tasks import FabricTaskError
    run_cmd = '{0} run --name {1} {2}'\
              .format(docker_exec_command, container_name, container_options)
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


def get_machine_distro():
    return _run_command('python -c "import platform, json, sys; '
                        'sys.stdout.write(\'{0}\\n\''
                        '.format(json.dumps(platform.dist())))"')


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
