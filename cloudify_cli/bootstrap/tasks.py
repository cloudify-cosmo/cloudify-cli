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
import urllib2

import fabric
import fabric.api
from fabric.context_managers import cd
from fabric.context_managers import settings

from cloudify import ctx
from cloudify_rest_client import CloudifyClient

REST_PORT = 80

# runtime properties manager blueprints may set to affect the behavior of
# the bootstrap task
PUBLIC_IP_RUNTIME_PROPERTY = 'public_ip'
PRIVATE_IP_RUNTIME_PROPERTY = 'private_ip'
PROVIDER_RUNTIME_PROPERTY = 'provider'

# internal runtime properties
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


def bootstrap(cloudify_packages, agent_local_key_path=None,
              agent_remote_key_path=None):

    if PUBLIC_IP_RUNTIME_PROPERTY in ctx.runtime_properties:
        manager_host_public_ip = \
            ctx.runtime_properties[PUBLIC_IP_RUNTIME_PROPERTY]
        with settings(host_string=manager_host_public_ip):
            _bootstrap(cloudify_packages, agent_local_key_path,
                       agent_remote_key_path)
    else:
        _bootstrap(cloudify_packages, agent_local_key_path,
                   agent_remote_key_path)


def _bootstrap(cloudify_packages, agent_local_key_path, agent_remote_key_path):

    global lgr
    lgr = ctx.logger

    manager_ip = fabric.api.env.host_string

    server_packages = cloudify_packages['server']
    agent_packages = cloudify_packages['agents']
    ui_included = 'ui_package_url' in server_packages

    lgr.info('initializing manager on the machine at {0}'.format(manager_ip))

    # get linux distribution to install and download
    # packages accordingly
    dist = _get_distro()  # dist is either the dist name or False
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
                      'configured location in the config file'.format(
                          agent_url))
            return False

    lgr.info('unpacking cloudify-core packages...')
    success = _unpack(
        PACKAGES_PATH['cloudify'],
        dist)
    if not success:
        lgr.error('failed to unpack cloudify-core package.')
        return False

    lgr.info('installing cloudify on {0}...'.format(manager_ip))
    success = _run_with_retries('sudo {0}/cloudify-components-bootstrap.sh'
                                .format(PACKAGES_PATH['components']))
    if not success:
        lgr.error('failed to install cloudify-components package.')
        return False

    # declare user to run celery. this is passed to the core package's
    # bootstrap script for installation.
    celery_user = fabric.api.env.user
    success = _run_with_retries('sudo {0}/cloudify-core-bootstrap.sh {1} {2}'
                                .format(PACKAGES_PATH['core'],
                                        celery_user,
                                        _get_endpoint_private_ip()))
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
    _upload_provider_context(agent_remote_key_path)
    _set_manager_endpoint_data()

    return True


def _set_manager_endpoint_data():
    ctx.runtime_properties[MANAGER_USER_RUNTIME_PROPERTY] = fabric.api.env.user
    ctx.runtime_properties[MANAGER_KEY_PATH_RUNTIME_PROPERTY] = \
        fabric.api.env.key_filename


def _get_endpoint_private_ip():
    return ctx.runtime_properties.get(PRIVATE_IP_RUNTIME_PROPERTY, ctx.host_ip)


def _copy_agent_key(agent_local_key_path=None,
                    agent_remote_key_path=None):
    ctx.logger.info('Copying agent key to management machine')
    if not agent_local_key_path:
        return
    agent_remote_key_path = agent_remote_key_path or '~/.ssh/agent_key.pem'
    agent_local_key_path = os.path.expanduser(agent_local_key_path)
    fabric.api.put(agent_local_key_path, agent_remote_key_path)
    return agent_remote_key_path


def _upload_provider_context(remote_agents_private_key_path):
    provider_context = \
        ctx.runtime_properties.get(PROVIDER_RUNTIME_PROPERTY, dict())
    cloudify_configuration = ctx.properties['cloudify']
    cloudify_configuration['cloudify_agent']['agent_key_path'] = \
        remote_agents_private_key_path
    provider_context['cloudify'] = cloudify_configuration
    ctx.runtime_properties[PROVIDER_RUNTIME_PROPERTY] = \
        provider_context

    manager_ip = fabric.api.env.host_string
    rest_client = CloudifyClient(manager_ip, REST_PORT)
    rest_client.manager.create_context('provider',
                                       provider_context)


def _run_with_retries(command):
    return fabric.api.run(command)


def _download_package(url, path, distro):
    if 'Ubuntu' in distro:
        return _run_with_retries('sudo wget {0} -P {1}'.format(
            path, url))
    elif 'centos' in distro:
        with cd(path):
            return _run_with_retries('sudo curl -O {0}')


def _unpack(path, distro):
    if 'Ubuntu' in distro:
        return _run_with_retries('sudo dpkg -i {0}/*.deb'.format(path))
    elif 'centos' in distro:
        return _run_with_retries('sudo rpm -i {0}/*.rpm'.format(path))


def _check_distro_type_match(url, distro):
    lgr.debug('checking distro-type match for url: {}'.format(url))
    ext = _get_ext(url)
    if not DISTRO_EXT[distro] == ext:
        lgr.error('wrong package type: '
                  '{} required. {} supplied. in url: {}'
                  .format(DISTRO_EXT[distro], ext, url))
        return False
    return True


def _get_distro():
    lgr.debug('identifying instance distribution...')
    return _run_with_retries(
        'python -c "import platform; print platform.dist()[0]"')


def _get_ext(url):
    lgr.debug('extracting file extension from url')
    filename = urllib2.unquote(url).decode('utf8').split('/')[-1]
    return os.path.splitext(filename)[1]
