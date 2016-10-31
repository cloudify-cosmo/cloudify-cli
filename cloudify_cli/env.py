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
from base64 import urlsafe_b64encode

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
        profile_dir = get_profile_dir(profile_name)
        shutil.rmtree(profile_dir)
    else:
        raise CloudifyCliError(
            'Profile {0} does not exist'.format(profile_name))


def is_profile_exists(profile_name):
    try:
        return os.path.isfile(get_context_path(profile_name))
    except CloudifyCliError:
        return False


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


def assert_credentials_set():
    error_msg = 'Manager {0} must be set in order to use a manager.\n' \
                'You can set it in the profile by running ' \
                '`cfy profiles set-{1}`, or you can set the `CLOUDIFY_{2}` ' \
                'environment variable.'
    if not get_username():
        raise CloudifyCliError(
            error_msg.format('Username', 'username', 'USERNAME')
        )
    if not get_password():
        raise CloudifyCliError(
            error_msg.format('Password', 'password', 'PASSWORD')
        )
    if not get_tenant_name():
        raise CloudifyCliError(
            error_msg.format('Tenant', 'tenant', 'TENANT')
        )


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
    is initialized. If not, it will just check that workenv is.
    """
    if profile_name:
        return get_profile_dir(profile_name) is not None
    else:
        return os.path.isfile(os.path.join(CLOUDIFY_WORKDIR, 'config.yaml'))


def get_context_path(profile_name, suppress_error=False):
    return os.path.join(
        get_profile_dir(profile_name, suppress_error),
        constants.CLOUDIFY_PROFILE_CONTEXT_FILE_NAME
    )


def get_profile_dir(profile_name=None, suppress_error=False):
    active_profile = profile_name or get_active_profile()
    if suppress_error or (active_profile and os.path.isdir(
            os.path.join(PROFILES_DIR, active_profile))):
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
                    tenant_name=None,
                    trust_all=False,
                    skip_version_check=False):
    rest_host = rest_host or profile.manager_ip
    rest_port = rest_port or profile.rest_port
    rest_protocol = rest_protocol or profile.rest_protocol
    username = username or get_username()
    password = password or get_password()
    tenant_name = tenant_name or get_tenant_name()
    trust_all = trust_all or get_ssl_trust_all()
    headers = get_auth_header(username, password)
    headers[constants.CLOUDIFY_TENANT_HEADER] = tenant_name

    if not username:
        raise CloudifyCliError('Command failed: Missing Username')

    if not password:
        raise CloudifyCliError('Command failed: Missing password')

    cert = get_ssl_cert()

    client = CloudifyClient(
        host=rest_host,
        port=rest_port,
        protocol=rest_protocol,
        headers=headers,
        cert=cert,
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


def build_manager_host_string(ssh_user='', ip=''):
    ssh_user = ssh_user or profile.ssh_user
    if not ssh_user:
        raise CloudifyCliError('Manager User is not set in '
                               'working directory settings')
    ip = ip or profile.manager_ip
    return '{0}@{1}'.format(ssh_user, ip)


def get_username():
    username = os.environ.get(constants.CLOUDIFY_USERNAME_ENV)
    if username and profile.manager_username:
        raise CloudifyCliError('Manager Username is set in profile *and* in '
                               'the `CLOUDIFY_USERNAME` env variable. Resolve '
                               'the conflict before continuing.\n'
                               'Either unset the env variable, or run '
                               '`cfy profiles unset-username`')
    return username or profile.manager_username


def get_password():
    password = os.environ.get(constants.CLOUDIFY_PASSWORD_ENV)
    if password and profile.manager_password:
        raise CloudifyCliError('Manager Password is set in profile *and* in '
                               'the `CLOUDIFY_PASSWORD` env variable. Resolve '
                               'the conflict before continuing.\n'
                               'Either unset the env variable, or run '
                               '`cfy profiles unset-password`')
    return password or profile.manager_password


def get_tenant_name():
    tenant = os.environ.get(constants.CLOUDIFY_TENANT_ENV)
    if tenant and profile.manager_tenant:
        raise CloudifyCliError('Manager Tenant is set in profile *and* in '
                               'the `CLOUDIFY_TENANT` env variable. Resolve '
                               'the conflict before continuing.\n'
                               'Either unset the env variable, or run '
                               '`cfy profiles unset-tenant`')
    return tenant or profile.manager_tenant


def get_default_rest_cert_local_path():
    return os.path.join(
        CLOUDIFY_WORKDIR,
        constants.PUBLIC_REST_CERT
    )


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
        self.bootstrap_state = 'Incomplete'
        self.manager_ip = profile_name
        self.ssh_key = None
        self._ssh_port = None
        self.ssh_user = None
        self.provider_context = dict()
        self.manager_username = None
        self.manager_password = None
        self.manager_tenant = constants.DEFAULT_TENANT_NAME
        self.rest_port = constants.DEFAULT_REST_PORT
        self.rest_protocol = constants.DEFAULT_REST_PROTOCOL

    def to_dict(self):
        return dict(
            bootstrap_state=self.bootstrap_state,
            manager_ip=self.manager_ip,
            ssh_key_path=self.ssh_key,
            ssh_port=self.ssh_port,
            ssh_user=self.ssh_user,
            provider_context=self.provider_context,
            manager_username=self.manager_username,
            manager_tenant=self.manager_tenant,
            rest_port=self.rest_port,
            rest_protocol=self.rest_protocol
        )

    @property
    def ssh_port(self):
        return self._ssh_port

    @ssh_port.setter
    def ssh_port(self, ssh_port):
        # If the port is int, we want to change it to a string. Otherwise,
        # leave None as is
        ssh_port = str(ssh_port) if ssh_port else None
        self._ssh_port = ssh_port

    def _get_context_path(self):
        init_path = get_profile_dir(self.manager_ip)
        context_path = os.path.join(
            init_path,
            constants.CLOUDIFY_PROFILE_CONTEXT_FILE_NAME)
        return context_path

    def save(self, destination=None):
        if not self.manager_ip:
            raise CloudifyCliError('No Manager IP set')

        workdir = destination or os.path.join(PROFILES_DIR, self.manager_ip)
        # Create a new file
        if not os.path.exists(workdir):
            os.makedirs(workdir)
        target_file_path = os.path.join(
            workdir,
            constants.CLOUDIFY_PROFILE_CONTEXT_FILE_NAME)

        with open(target_file_path, 'w') as f:
            f.write(yaml.dump(self))


def get_auth_header(username, password):
    header = {}

    if username and password:
        credentials = '{0}:{1}'.format(username, password)
        encoded_credentials = urlsafe_b64encode(credentials)
        header = {
            constants.CLOUDIFY_AUTHENTICATION_HEADER:
                constants.BASIC_AUTH_PREFIX + ' ' + encoded_credentials}

    return header

profile = get_profile_context(suppress_error=True)
