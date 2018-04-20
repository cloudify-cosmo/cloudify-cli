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
import types
import shutil
import pkgutil
import getpass
import tempfile
import itertools
from base64 import urlsafe_b64encode

import yaml
import requests

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.client import HTTPClient
from cloudify_rest_client.exceptions import (CloudifyClientError,
                                             RemovedFromCluster,
                                             NotClusterMaster)
from . import constants
from .exceptions import CloudifyCliError

_ENV_NAME = 'manager'
DEFAULT_LOG_FILE = os.path.expanduser(
    '{0}/cloudify-{1}/cloudify-cli.log'.format(
        tempfile.gettempdir(), getpass.getuser()))

CLOUDIFY_WORKDIR = os.path.join(
    os.environ.get('CFY_WORKDIR', os.path.expanduser('~')),
    constants.CLOUDIFY_BASE_DIRECTORY_NAME)
PROFILES_DIR = os.path.join(CLOUDIFY_WORKDIR, 'profiles')
ACTIVE_PRO_FILE = os.path.join(CLOUDIFY_WORKDIR, 'active.profile')
MULTIPLE_LOCAL_BLUEPRINTS = (
    os.environ.get('CFY_MULTIPLE_BLUEPRINTS', 'true') == 'true')
CLUSTER_RETRY_INTERVAL = 5


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
    global profile
    with open(ACTIVE_PRO_FILE, 'w+') as active_profile:
        active_profile.write(profile_name)
    profile = get_profile_context(profile_name, suppress_error=True)


def get_active_profile():
    if os.path.isfile(ACTIVE_PRO_FILE):
        with open(ACTIVE_PRO_FILE) as active_profile:
            return active_profile.read().strip()
    else:
        # We return None explicitly as no profile is active.
        return None


def get_profile_names():
    # TODO: This is too.. ambiguous. We should change it so there are
    # no exclusions.
    excluded = ['local']
    profile_names = [item for item in os.listdir(PROFILES_DIR)
                     if item not in excluded and not item.startswith('.')]

    return profile_names


def assert_manager_active():
    if not is_manager_active():
        raise CloudifyCliError(
            'This command is only available when using a manager. '
            'You need to run run `cfy profiles use MANAGER_IP`')


def assert_local_active():
    if is_manager_active():
        raise CloudifyCliError(
            'This command is not available when using a manager. '
            'You can run `cfy profiles use local` to stop using a manager.')


def assert_credentials_set():
    error_msg = 'Manager {0} must be set in order to use a manager.\n' \
                'You can set it in the profile by running ' \
                '`cfy profiles set {1}`, or you can set the `CLOUDIFY_{2}` ' \
                'environment variable.'
    if not get_username():
        raise CloudifyCliError(
            error_msg.format('Username', '--manager-username', 'USERNAME')
        )
    if not get_password():
        raise CloudifyCliError(
            error_msg.format('Password', '--manager-password', 'PASSWORD')
        )
    if not get_tenant_name():
        raise CloudifyCliError(
            error_msg.format('Tenant', '--manager-tenant', 'TENANT')
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
    """Check if a profile or an environment is initialized.

    If profile_name is provided, it will check if the profile
    is initialized. If not, it will just check that workenv is.
    """
    if profile_name:
        return get_profile_dir(profile_name) is not None
    else:
        return os.path.isfile(os.path.join(CLOUDIFY_WORKDIR, 'config.yaml'))


def get_context_path(profile_name, suppress_error=False):
    base_dir = get_profile_dir(profile_name, suppress_error)
    if not base_dir:
        return
    return os.path.join(
        base_dir,
        constants.CLOUDIFY_PROFILE_CONTEXT_FILE_NAME
    )


def get_profile_dir(profile_name=None, suppress_error=False):
    active_profile = profile_name or get_active_profile()
    if active_profile and os.path.isdir(
            os.path.join(PROFILES_DIR, active_profile)):
        return os.path.join(PROFILES_DIR, active_profile)
    elif suppress_error:
        return
    else:
        raise CloudifyCliError('Profile directory does not exist')


def raise_uninitialized():
    error = CloudifyCliError(
        'Cloudify environment is not initialized')
    error.possible_solutions = [
        "Run 'cfy init'"
    ]
    raise error


def get_rest_client(client_profile=None,
                    rest_host=None,
                    rest_port=None,
                    rest_protocol=None,
                    rest_cert=None,
                    username=None,
                    password=None,
                    tenant_name=None,
                    trust_all=False,
                    skip_version_check=False,
                    cluster=None):
    if client_profile is None:
        client_profile = profile
    rest_host = rest_host or client_profile.manager_ip
    rest_port = rest_port or client_profile.rest_port
    rest_protocol = rest_protocol or client_profile.rest_protocol
    rest_cert = rest_cert or get_ssl_cert(client_profile)
    username = username or get_username(client_profile)
    password = password or get_password(client_profile)
    tenant_name = tenant_name or get_tenant_name(client_profile)
    trust_all = trust_all or get_ssl_trust_all()
    headers = get_auth_header(username, password)
    headers[constants.CLOUDIFY_TENANT_HEADER] = tenant_name
    cluster = cluster or client_profile.cluster

    if not username:
        raise CloudifyCliError('Command failed: Missing Username')

    if not password:
        raise CloudifyCliError('Command failed: Missing password')

    if cluster:
        client = CloudifyClusterClient(
            host=rest_host,
            port=rest_port,
            protocol=rest_protocol,
            headers=headers,
            cert=rest_cert,
            trust_all=trust_all,
            profile=client_profile)

    else:
        client = CloudifyClient(
            host=rest_host,
            port=rest_port,
            protocol=rest_protocol,
            headers=headers,
            cert=rest_cert,
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
        raise CloudifyCliError('Manager `ssh_user` is not set '
                               'in Cloudify CLI settings')
    ip = ip or profile.manager_ip
    return '{0}@{1}'.format(ssh_user, ip)


def get_default_rest_cert_local_path():
    base_dir = get_profile_dir(suppress_error=True) or CLOUDIFY_WORKDIR
    return os.path.join(base_dir, constants.PUBLIC_REST_CERT)


def get_username(from_profile=None):
    if from_profile is None:
        from_profile = profile
    username = os.environ.get(constants.CLOUDIFY_USERNAME_ENV)
    if username and from_profile.manager_username:
        raise CloudifyCliError('Manager Username is set in profile *and* in '
                               'the `CLOUDIFY_USERNAME` env variable. Resolve '
                               'the conflict before continuing.\n'
                               'Either unset the env variable, or run '
                               '`cfy profiles unset --manager-username`')
    return username or from_profile.manager_username


def get_password(from_profile=None):
    if from_profile is None:
        from_profile = profile
    password = os.environ.get(constants.CLOUDIFY_PASSWORD_ENV)
    if password and from_profile.manager_password:
        raise CloudifyCliError('Manager Password is set in profile *and* in '
                               'the `CLOUDIFY_PASSWORD` env variable. Resolve '
                               'the conflict before continuing.\n'
                               'Either unset the env variable, or run '
                               '`cfy profiles unset --manager-password`')
    return password or from_profile.manager_password


def get_tenant_name(from_profile=None):
    if from_profile is None:
        from_profile = profile
    tenant = os.environ.get(constants.CLOUDIFY_TENANT_ENV)
    if tenant and from_profile.manager_tenant:
        raise CloudifyCliError('Manager Tenant is set in profile *and* in '
                               'the `CLOUDIFY_TENANT` env variable. Resolve '
                               'the conflict before continuing.\n'
                               'Either unset the env variable, or run '
                               '`cfy profiles unset --manager-tenant`')
    return tenant or from_profile.manager_tenant


def get_ssl_cert(from_profile=None):
    """Return the path to a local copy of the manager's public certificate.

    :return: If the LOCAL_REST_CERT_FILE env var was set by the user *or* if
    `rest_certificate` is set in the profile - use it,
    If it wasn't set, check if the certificate file is found in its default
    location. If so - use it, otherwise - return None
    Note that if it is set in both profile and env var - an error will be
    raised
    """
    if from_profile is None:
        from_profile = profile
    cert = os.environ.get(constants.LOCAL_REST_CERT_FILE)
    if cert and from_profile.rest_certificate:
        raise CloudifyCliError('Rest Certificate is set in profile *and* in '
                               'the `LOCAL_REST_CERT_FILE` env variable. '
                               'Resolve the conflict before continuing.\n'
                               'Either unset the env variable, or run '
                               '`cfy profiles unset --rest_certificate`')
    if cert or from_profile.rest_certificate:
        return cert or from_profile.rest_certificate
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
    version_data['ip'] = profile.manager_ip
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
        # Note that __init__ is not called when loading from yaml.
        # When adding a new ProfileContext attribute, make sure that
        # all methods handle the case when the attribute is missing
        self._profile_name = profile_name
        self.manager_ip = None
        self.ssh_key = None
        self._ssh_port = None
        self.ssh_user = None
        self.provider_context = dict()
        self.manager_username = None
        self.manager_password = None
        self.manager_tenant = None
        self.rest_port = constants.DEFAULT_REST_PORT
        self.rest_protocol = constants.DEFAULT_REST_PROTOCOL
        self.rest_certificate = None
        self._cluster = []

    def to_dict(self):
        return dict(
            name=self.profile_name,
            manager_ip=self.manager_ip,
            ssh_key_path=self.ssh_key,
            ssh_port=self.ssh_port,
            ssh_user=self.ssh_user,
            provider_context=self.provider_context,
            manager_username=self.manager_username,
            manager_tenant=self.manager_tenant,
            rest_port=self.rest_port,
            rest_protocol=self.rest_protocol,
            rest_certificate=self.rest_certificate,
            cluster=self.cluster
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

    @property
    def profile_name(self):
        return getattr(self, '_profile_name', None) \
            or getattr(self, 'manager_ip', None)

    @profile_name.setter
    def profile_name(self, profile_name):
        self._profile_name = profile_name

    @property
    def cluster(self):
        # default the ._cluster attribute here, so that all callers can use it
        # as just ._cluster, even if it's not present in the source yaml
        if not hasattr(self, '_cluster'):
            self._cluster = []
        return self._cluster

    @cluster.setter
    def cluster(self, cluster):
        self._cluster = cluster

    def _get_context_path(self):
        init_path = get_profile_dir(self.profile_name)
        context_path = os.path.join(
            init_path,
            constants.CLOUDIFY_PROFILE_CONTEXT_FILE_NAME)
        return context_path

    @property
    def workdir(self):
        return os.path.join(PROFILES_DIR, self.profile_name)

    def save(self, destination=None):
        if not self.profile_name:
            raise CloudifyCliError('No profile name or Manager IP set')

        workdir = destination or self.workdir
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


# attributes that can differ for each node in a cluster. Those will be updated
# in the profile when we switch to a new master.
# Dicts with these keys live in profile.cluster, and are added there during
# either `cfy cluster update-profile` (in which case some of them might be
# missing, eg. ssh_*), or during a `cfy cluster join`.
# If a value is missing, we will use the value from the last active manager.
# Only the IP is required.
# Note that not all attributes are allowed - username/password will be
# the same for every node in the cluster.
CLUSTER_NODE_ATTRS = ['manager_ip', 'rest_port', 'rest_protocol', 'ssh_port',
                      'ssh_user', 'ssh_key']


class ClusterHTTPClient(HTTPClient):
    default_timeout_sec = (5, None)

    def __init__(self, *args, **kwargs):
        profile = kwargs.pop('profile')
        super(ClusterHTTPClient, self).__init__(*args, **kwargs)
        if not profile.cluster:
            raise ValueError('Cluster client invoked for an empty cluster!')
        self._cluster = list(profile.cluster)
        self._profile = profile
        first_node = self._cluster[0]
        self.cert = first_node.get('cert') or self.cert
        self.trust_all = first_node.get('trust_all') or self.trust_all

    def do_request(self, *args, **kwargs):
        # this request can be retried for each manager - if the data is
        # a generator, we need to copy it, so we can send it more than once
        copied_data = None
        if isinstance(kwargs.get('data'), types.GeneratorType):
            copied_data = itertools.tee(kwargs.pop('data'),
                                        len(self._cluster))

        if kwargs.get('timeout') is None:
            kwargs['timeout'] = self.default_timeout_sec

        for node_index, node in list(enumerate(self._profile.cluster)):
            self._use_node(node)
            if copied_data is not None:
                kwargs['data'] = copied_data[node_index]

            try:
                return super(ClusterHTTPClient, self).do_request(*args,
                                                                 **kwargs)
            except (RemovedFromCluster, NotClusterMaster,
                    requests.exceptions.ConnectionError):
                continue

        raise CloudifyClientError('No active node in the cluster!')

    def _use_node(self, node):
        if node['manager_ip'] == self.host:
            return
        self.host = node['manager_ip']
        for attr in ['rest_port', 'rest_protocol', 'trust_all', 'cert']:
            new_value = node.get(attr)
            if new_value:
                setattr(self, attr, new_value)
        self._update_profile(node)

    def _update_profile(self, node):
        """Put the node at the start of the cluster list in profile.

        The client tries nodes in the order of the cluster list, so putting
        the node first will make the client try it first next time. This makes
        the client always try the last-known-master first.
        """
        self._profile.cluster.remove(node)
        self._profile.cluster = [node] + self._profile.cluster
        for node_attr in CLUSTER_NODE_ATTRS:
            if node_attr in node:
                setattr(self._profile, node_attr, node[node_attr])
        self._profile.save()


class CloudifyClusterClient(CloudifyClient):
    """A CloudifyClient that will retry the queries with the current master.

    When a request fails with a connection error, or with a "not cluster
    master" error, this will keep trying with every node in the cluster,
    until it finds the cluster master.

    When the master is found, the profile will be updated with its address.
    """
    def __init__(self, profile, *args, **kwargs):
        self._profile = profile
        super(CloudifyClusterClient, self).__init__(*args, **kwargs)

    def client_class(self, *args, **kwargs):
        kwargs.setdefault('profile', self._profile)
        return ClusterHTTPClient(*args, **kwargs)


def build_fabric_env(manager_ip, ssh_user, ssh_port, ssh_key_path):
    return {
        "host_string": manager_ip,
        "user": ssh_user,
        "port": ssh_port,
        "key_filename": ssh_key_path
    }


profile = get_profile_context(suppress_error=True)
