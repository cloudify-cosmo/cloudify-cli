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
import json
import shutil
import pkgutil
import getpass
import tempfile

import yaml
from itsdangerous import base64_encode

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

from . import constants
from .exceptions import CloudifyCliError


DEFAULT_LOG_FILE = os.path.expanduser(
    '{0}/cloudify-{1}/cloudify-cli.log'.format(
        tempfile.gettempdir(), getpass.getuser()))

CLOUDIFY_WORKDIR = os.path.join(
    os.environ.get('CFY_WORKDIR', os.path.expanduser('~')),
    constants.CLOUDIFY_BASE_DIRECTORY_NAME)
PROFILES_DIR = os.path.join(CLOUDIFY_WORKDIR, 'profiles')
ACTIVE_PRO_FILE = os.path.join(CLOUDIFY_WORKDIR, 'active.profile')
MULTIPLE_LOCAL_BLUEPRINTS = os.environ.get('CFY_MULTIPLE_BLUEPRINTS') == 'true'


def delete_profile(profile_name):
    if is_profile_exists(profile_name):
        shutil.rmtree(profile_dir)
    else:
        raise CloudifyCliError(
            'Profile {0} does not exist'.format(profile_name))


def is_profile_exists(profile_name):
    return os.path.isfile(os.path.join(PROFILES_DIR, profile_name, 'context'))


def assert_profile_exists(profile_name):
    if not is_profile_exists(profile_name):
        raise CloudifyCliError(
            'Profile {0} does not exist. You can run `cfy init {0}` to '
            'create the profile.'.format(profile_name))


def set_active_profile(profile_name):
    with open(ACTIVE_PRO_FILE, 'w+') as active_profile:
        active_profile.write(profile_name)


def get_active_profile():
    if os.path.isfile(ACTIVE_PRO_FILE):
        with open(ACTIVE_PRO_FILE) as active_profile:
            return active_profile.read().strip()
    else:
        # We return None explicitly as no profile is active.
        return None


def assert_manager_active():
    if not is_manager_active():
        raise CloudifyCliError(
            'This command is only available when using a manager. '
            'You can either bootstrap a manager or run `cfy use MANAGER_IP`')


def assert_local_active():
    if is_manager_active():
        raise CloudifyCliError(
            'This command is not available when using a manager. '
            'You can run `cfy use local` to stop using a manager.')


def is_manager_active():
    active_profile = get_active_profile()
    if not active_profile:
        return False

    if active_profile == 'local':
        return False

    p = get_profile_context(active_profile, suppress_error=True)
    if not (p and p.manager_ip):
        return False
    return True


def get_profile_context(profile_name=None, suppress_error=False):
    profile_name = profile_name or get_active_profile()
    if profile_name == 'local':
        if suppress_error:
            return ProfileContext()
        raise CloudifyCliError('Local profile does not have context')
    try:
        path = get_context_path(profile_name)
        with open(path) as f:
            return yaml.load(f.read())
    except CloudifyCliError:
        if suppress_error:
            return ProfileContext()
        raise


def is_initialized(profile_name=None):
    """Checks if a profile or an environment is initialized.

    If profile_name is provided, it will check if the profile
    is initialzed. If not, it will just check that the `local`
    profile is.
    """
    if profile_name:
        return get_profile_dir(profile_name) is not None
    else:
        return os.path.isdir(CLOUDIFY_WORKDIR)


def get_context_path(profile_name):
    init_path = get_profile_dir(profile_name)
    context_path = os.path.join(
        init_path,
        constants.CLOUDIFY_PROFILE_CONTEXT_FILE_NAME)
    return context_path


def get_profile_dir(profile_name=None):
    active_profile = profile_name or get_active_profile()
    if active_profile and os.path.isdir(
            os.path.join(PROFILES_DIR, active_profile)):
        return os.path.join(PROFILES_DIR, active_profile)
    else:
        raise CloudifyCliError('Profile directory does not exist')


def raise_uninitialized():
    error = CloudifyCliError(
        'Cloudify environment is not initialized')
    error.possible_solutions = [
        "Run 'cfy init'"
    ]
    raise error


def get_rest_client(rest_host=None,
                    rest_port=None,
                    rest_protocol=None,
                    username=None,
                    password=None,
                    trust_all=False,
                    skip_version_check=False):
    rest_host = rest_host or profile.manager_ip
    rest_port = rest_port or profile.rest_port
    rest_protocol = rest_protocol or profile.rest_protocol
    username = username or get_username()
    password = password or get_password()
    trust_all = trust_all or get_ssl_trust_all()
    headers = get_auth_header(username, password)

    # TODO: PUT BACK SSL CERT!!!!!!!!!!!!!!!!!!!!!!!!!
    # cert = get_ssl_cert()

    client = CloudifyClient(
        host=rest_host,
        port=rest_port,
        protocol=rest_protocol,
        headers=headers,
        # cert=cert,
        trust_all=trust_all)

    # TODO: Put back version check after we've solved the problem where
    # a new CLI is used with an older manager on `cfy upgrade`.
    if skip_version_check or True:
        return client

    cli_version, manager_version = get_cli_manager_versions(client)

    if cli_version == manager_version:
        return client
    elif not manager_version:
        return client
    else:
        raise CloudifyCliError(
            'CLI and manager versions do not match\n'
            'CLI Version: {0}\n'
            'Manager Version: {1}'.format(cli_version, manager_version))


def build_manager_host_string(user='', ip=''):
    user = user or profile.manager_user
    if not user:
        raise CloudifyCliError('Manager User is not set in '
                               'working directory settings')
    ip = ip or profile.manager_ip
    return '{0}@{1}'.format(user, ip)


def get_username():
    return os.environ.get(constants.CLOUDIFY_USERNAME_ENV)


def get_password():
    return os.environ.get(constants.CLOUDIFY_PASSWORD_ENV)


def get_default_rest_cert_local_path():
    return os.path.join(get_profile_dir(), constants.PUBLIC_REST_CERT)


def get_ssl_cert():
    """Return the path to a local copy of the manager's public certificate.

    :return: If the LOCAL_REST_CERT_FILE env var was set by the user - use it,
    If it wasn't set, check if the certificate file is found in its default
    location. If so - use it, otherwise - return None
    """
    if os.environ.get(constants.LOCAL_REST_CERT_FILE):
        return os.environ.get(constants.LOCAL_REST_CERT_FILE)

    default_cert_file = get_default_rest_cert_local_path()
    return default_cert_file if os.path.isfile(default_cert_file) else None


def get_ssl_trust_all():
    trust_all = os.environ.get(constants.CLOUDIFY_SSL_TRUST_ALL)
    if trust_all is not None and len(trust_all) > 0:
        return True
    return False


def get_version():
    version_data = get_version_data()
    return version_data['version']


def get_version_data():
    data = pkgutil.get_data('cloudify_cli', 'VERSION')
    return json.loads(data)


def get_manager_version_data(rest_client=None):
    if not rest_client:
        if not get_profile_context(suppress_error=True):
            return None
        try:
            rest_client = get_rest_client(skip_version_check=True)
        except CloudifyCliError:
            return None
    try:
        version_data = rest_client.manager.get_version()
    except CloudifyClientError:
        return None
    version_data['ip'] = rest_client.host
    return version_data


def get_cli_manager_versions(rest_client):
    manager_version_data = get_manager_version_data(rest_client)
    cli_version = get_version_data().get('version')

    if not manager_version_data:
        return cli_version, None
    else:
        manager_version = manager_version_data.get('version')
        return cli_version, manager_version


class ProfileContext(yaml.YAMLObject):
    yaml_tag = u'!CloudifyProfileContext'
    yaml_loader = yaml.Loader

    def __init__(self, profile_name=None):
        self._bootstrap_state = None
        self._manager_ip = profile_name
        self._manager_key = None
        self._manager_port = None
        self._manager_user = None
        self._provider_context = dict()
        self._rest_port = constants.DEFAULT_REST_PORT
        self._rest_protocol = constants.DEFAULT_REST_PROTOCOL

    @property
    def bootstrap_state(self):
        return self._bootstrap_state

    @bootstrap_state.setter
    def bootstrap_state(self, bootstrap_state):
        self._bootstrap_state = bootstrap_state

    @property
    def manager_ip(self):
        return self._manager_ip

    @manager_ip.setter
    def manager_ip(self, manager_host):
        self._manager_ip = manager_host

    @property
    def manager_key(self):
        return self._manager_key

    @manager_key.setter
    def manager_key(self, manager_key):
        self._manager_key = manager_key

    @property
    def manager_port(self):
        return self._manager_port

    @manager_port.setter
    def manager_port(self, manager_port):
        # If the port is int, we want to change it to a string. Otherwise,
        # leave None as is
        manager_port = str(manager_port) if manager_port else None
        self._manager_port = manager_port

    @property
    def manager_user(self):
        return self._manager_user

    @manager_user.setter
    def manager_user(self, _manager_user):
        self._manager_user = _manager_user

    @property
    def provider_context(self):
        return self._provider_context

    @provider_context.setter
    def provider_context(self, provider_context):
        self._provider_context = provider_context

    def remove_manager_server_context(self):
        self._manager_ip = None

    @property
    def rest_port(self):
        return self._rest_port

    @rest_port.setter
    def rest_port(self, rest_port):
        self._rest_port = rest_port

    @property
    def rest_protocol(self):
        return self._rest_protocol

    @rest_protocol.setter
    def rest_protocol(self, rest_protocol):
        self._rest_protocol = rest_protocol

    def _get_context_path(self):
        init_path = get_profile_dir(self.manager_ip)
        context_path = os.path.join(
            init_path,
            constants.CLOUDIFY_PROFILE_CONTEXT_FILE_NAME)
        return context_path

    def save(self):
        if not self.manager_ip:
            raise CloudifyCliError('No Manager IP set')

        workdir = os.path.join(PROFILES_DIR, self.manager_ip)
        # create a new file
        if not os.path.exists(workdir):
            os.makedirs(workdir)
        target_file_path = os.path.join(
            workdir,
            constants.CLOUDIFY_PROFILE_CONTEXT_FILE_NAME)

        with open(target_file_path, 'w') as f:
            f.write(yaml.dump(self))


def get_auth_header(username, password):
    header = None

    if username and password:
        credentials = '{0}:{1}'.format(username, password)
        header = {
            constants.CLOUDIFY_AUTHENTICATION_HEADER:
                constants.BASIC_AUTH_PREFIX + ' ' + base64_encode(credentials)}

    return header

profile = get_profile_context(suppress_error=True)
