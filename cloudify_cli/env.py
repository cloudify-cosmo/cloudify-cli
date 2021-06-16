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
import errno
import types
import shutil
import getpass
import tempfile
import itertools
from base64 import b64encode
from contextlib import contextmanager

import yaml
import requests

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.client import HTTPClient
from cloudify.cluster_status import CloudifyNodeType
from cloudify_rest_client.utils import is_kerberos_env
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify.utils import ipv6_url_compat

from . import constants
from .exceptions import CloudifyCliError

try:
    from fabric import Connection
    from paramiko import AuthenticationException
except ImportError:
    Connection = None


_ENV_NAME = 'manager'
DEFAULT_LOG_FILE = os.path.expanduser(
    '{0}/cloudify-{1}/cloudify-cli.log'.format(
        tempfile.gettempdir(), getpass.getuser()))

CLOUDIFY_WORKDIR = os.path.join(
    os.environ.get('CFY_WORKDIR', os.path.expanduser('~')),
    constants.CLOUDIFY_BASE_DIRECTORY_NAME)
PROFILES_DIR = os.path.join(CLOUDIFY_WORKDIR, 'profiles')
ACTIVE_PROFILE = os.path.join(CLOUDIFY_WORKDIR, 'active.profile')
CLUSTER_RETRY_INTERVAL = 5


def delete_profile(profile_name):
    if is_profile_exists(profile_name):
        profile_dir = get_profile_dir(profile_name)
        if profile_dir:
            shutil.rmtree(profile_dir)


def is_profile_exists(profile_name):
    base_dir = get_profile_dir(profile_name)
    if not base_dir:
        return False
    return (os.path.isfile(os.path.join(base_dir, 'context.json')) or
            os.path.isfile(os.path.join(base_dir, 'context')))


def assert_profile_exists(profile_name):
    if not is_profile_exists(profile_name):
        raise CloudifyCliError(
            'Profile {0} does not exist. You can run `cfy init {0}` to '
            'create the profile.'.format(profile_name))


def set_active_profile(profile_name):
    global profile
    with open(ACTIVE_PROFILE, 'w+') as active_profile:
        active_profile.write(profile_name)
    profile = get_profile_context(profile_name, suppress_error=True)


def get_active_profile():
    try:
        with open(ACTIVE_PROFILE) as active_profile:
            return active_profile.read().strip()
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
        return None


def set_target_manager(manager_host):
    global target_manager
    target_manager = manager_host


def get_target_manager():
    return target_manager


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
            'Please use the `cfy profiles use` command to connect '
            'to a Cloudify Manager.')


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
    if not get_kerberos_env():
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
    if profile_name == 'local':
        return ProfileContext({}, profile_name='local')

    profile_name = profile_name or get_active_profile()
    loaded = None
    path = get_context_path(profile_name)
    if path:
        try:
            with open(path) as f:
                loaded = json.load(f)
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise

    if not loaded:
        loaded = _try_load_yaml_profile(profile_name)

    if not loaded:
        if suppress_error:
            return ProfileContext({})
        raise CloudifyCliError('No context for profile {0}'
                               .format(profile_name))
    return ProfileContext(loaded, profile_name)


class _ProfileLoader(yaml.SafeLoader):
    """A yaml Loader that can load Cloudify 5.1 profiles

    It supports python/unicode, which was commonly present in py2-created
    profiles.
    """


def _load_str(loader, node):
    return node.value


_ProfileLoader.add_constructor(u'tag:yaml.org,2002:python/unicode', _load_str)


def _try_load_yaml_profile(profile_name):
    """Try to load the profile from the yaml context file.

    This keeps compatibility with Cloudify 5.1 and earlier, who stored
    the context in a yaml file. We will still load them, but we won't
    store them anymore.
    """
    base_dir = get_profile_dir(profile_name)
    if not base_dir:
        return
    try:
        with open(os.path.join(base_dir, 'context')) as f:
            # dropping the object tag from yaml, so that we load the
            # yaml as just a dict and not as an object
            data = f.read().replace('!CloudifyProfileContext', '')
            context = yaml.load(data, Loader=_ProfileLoader)
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
        return
    return context


def config_initialized_with_logging():
    """
    This is for the Windows agent: plugin URLs from
    import_resolver are written to config.yaml during installation, so we can
    have a scenario where config exists but has no logger paths defined.
    """
    has_logging = False
    if os.path.isfile(os.path.join(CLOUDIFY_WORKDIR, 'config.yaml')):
        with open(os.path.join(CLOUDIFY_WORKDIR, 'config.yaml'), 'r') as f:
            has_logging = ('logging' in f.read())
    return has_logging


def is_initialized(profile_name=None):
    """
    Check if a profile or an environment is initialized.

    If profile_name is provided, it will check if the profile
    is initialized. If not, it will just check that workenv is.
    """
    if profile_name:
        return get_profile_dir(profile_name) is not None
    else:
        return config_initialized_with_logging()


def get_context_path(profile_name):
    base_dir = get_profile_dir(profile_name)
    if not base_dir:
        return
    return os.path.join(base_dir, 'context.json')


def get_profile_dir(profile_name=None):
    active_profile = profile_name or get_active_profile()
    if active_profile and os.path.isdir(
            os.path.join(PROFILES_DIR, active_profile)):
        return os.path.join(PROFILES_DIR, active_profile)


def raise_uninitialized():
    error = CloudifyCliError(
        'Cloudify environment is not initialized')
    error.possible_solutions = [
        "Run 'cfy init'"
    ]
    raise error


def is_cluster(client_profile=None):
    if client_profile is None:
        client_profile = profile
    return (not isinstance(client_profile.cluster, list) and
            client_profile.cluster.get(CloudifyNodeType.MANAGER))


def get_rest_client(client_profile=None,
                    rest_host=None,
                    rest_port=None,
                    rest_protocol=None,
                    rest_cert=None,
                    username=None,
                    password=None,
                    tenant_name=None,
                    trust_all=False,
                    cluster=None,
                    kerberos_env=None):
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
    cluster = cluster or is_cluster(client_profile)
    kerberos_env = kerberos_env \
        if kerberos_env is not None else client_profile.kerberos_env

    if kerberos_env is False \
            or (kerberos_env is None and not is_kerberos_env()):
        if not username:
            raise CloudifyCliError('Command failed: Missing Username')
        if not password:
            raise CloudifyCliError('Command failed: Missing password')

    if cluster:
        client = CloudifyClusterClient(host=rest_host,
                                       port=rest_port,
                                       protocol=rest_protocol,
                                       headers=headers,
                                       cert=rest_cert,
                                       trust_all=trust_all,
                                       profile=client_profile,
                                       kerberos_env=kerberos_env)
    else:
        client = CloudifyClient(host=rest_host,
                                port=rest_port,
                                protocol=rest_protocol,
                                headers=headers,
                                cert=rest_cert,
                                trust_all=trust_all,
                                kerberos_env=kerberos_env)
    return client


def build_manager_host_string(ssh_user='', ip=''):
    ip = ip or profile.manager_ip
    return build_host_string(ip, ssh_user)


def build_host_string(ip, ssh_user=''):
    ssh_user = ssh_user or profile.ssh_user
    if not ssh_user:
        raise CloudifyCliError('`ssh_user` is not set in the current '
                               'profile. Please run '
                               '`cfy profiles set --ssh-user <ssh-user>`.')
    return '{0}@{1}'.format(ssh_user, ip)


def get_default_rest_cert_local_path():
    base_dir = get_profile_dir() or CLOUDIFY_WORKDIR
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


def get_kerberos_env(from_profile=None):
    if from_profile is None:
        from_profile = profile
    return from_profile.kerberos_env


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


def get_manager_version_data(rest_client=None):
    if not rest_client:
        if not get_profile_context(suppress_error=True):
            return None
        try:
            rest_client = get_rest_client()
        except CloudifyCliError:
            return None
    try:
        version_data = rest_client.manager.get_version()
    except CloudifyClientError:
        return None
    version_data['ip'] = profile.manager_ip
    return version_data


class ProfileContext(object):
    def __init__(self, context=None, profile_name=None):
        self._context = {
            'name': profile_name,
            'manager_ip': None,
            'ssh_key': None,
            'ssh_port': 22,
            'ssh_user': None,
            'provider_context': {},
            'manager_username': None,
            'manager_password': None,
            'manager_tenant': None,
            'rest_port': constants.DEFAULT_REST_PORT,
            'rest_protocol': constants.DEFAULT_REST_PROTOCOL,
            'rest_certificate': None,
            'kerberos_env': False,
            'cluster': {}
        }
        if context:
            self._context.update(context)

    def __getattr__(self, name):
        return self._context[name]

    def __setattr__(self, name, value):
        if name in ['_context', 'profile_name']:
            super(ProfileContext, self).__setattr__(name, value)
        else:
            self._context[name] = value

    def to_dict(self):
        ctx = self._context.copy()
        ctx['name'] = self.profile_name
        return ctx

    @property
    def profile_name(self):
        return self._context['name'] or self._context['manager_ip']

    @profile_name.setter
    def profile_name(self, value):
        self._context['name'] = value

    @property
    def workdir(self):
        return os.path.join(PROFILES_DIR, self.profile_name)

    def save(self, destination=None):
        if not self.profile_name:
            raise CloudifyCliError('No profile name or Manager IP set')

        workdir = destination or self.workdir
        # Create a new file
        if not os.path.exists(workdir):
            os.makedirs(workdir, mode=0o700)
        target_file_path = os.path.join(
            workdir,
            'context.json')
        with open(target_file_path, 'w') as f:
            json.dump(self.to_dict(), f, sort_keys=True, indent=4)
            f.write('\n')


def get_auth_header(username, password):
    header = {}

    if username and password:
        # encode/decode just to allow b64encode, which requires bytes
        credentials = '{0}:{1}'.format(username, password).encode('utf-8')
        encoded_credentials = b64encode(credentials).decode('utf-8')
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
CLUSTER_NODE_ATTRS = ['host_ip', 'host_type', 'rest_port', 'rest_protocol',
                      'ssh_port', 'ssh_user', 'ssh_key']
_TRY_NEXT_NODE = object()


class ClusterHTTPClient(HTTPClient):

    def __init__(self, *args, **kwargs):
        profile = kwargs.pop('profile')
        super(ClusterHTTPClient, self).__init__(*args, **kwargs)
        if not profile.cluster:
            raise ValueError('Cluster client invoked for an empty cluster!')
        self._cluster = list(profile.cluster.get(CloudifyNodeType.MANAGER))
        self._profile = profile
        first_node = self._cluster[0]
        self.cert = first_node.get('cert') or self.cert
        self.trust_all = first_node.get('trust_all') or self.trust_all
        self.default_timeout_sec = self.default_timeout_sec or (5, None)

    def do_request(self, *args, **kwargs):
        # this request can be retried for each manager - if the data is
        # a generator, we need to copy it, so we can send it more than once
        copied_data = None
        if isinstance(kwargs.get('data'), types.GeneratorType):
            copied_data = itertools.tee(kwargs.pop('data'),
                                        len(self._cluster) + 1)

        if kwargs.get('timeout') is None:
            kwargs['timeout'] = self.default_timeout_sec

        if copied_data is not None:
            kwargs['data'] = copied_data[-1]

        manager_host = get_target_manager()
        if manager_host:
            self.host = ipv6_url_compat(manager_host)
            return super(ClusterHTTPClient, self).do_request(*args, **kwargs)

        # First try with the main manager ip given when creating the profile
        # with `cfy profiles use`
        self.host = ipv6_url_compat(self._profile.manager_ip)
        response = self._try_do_request(*args, **kwargs)
        if response is not _TRY_NEXT_NODE:
            return response

        for node_index, node in list(enumerate(
                self._profile.cluster[CloudifyNodeType.MANAGER])):
            if self._profile.manager_ip in [node['host_ip'], node['hostname']]:
                continue
            self._use_node(node)
            if copied_data is not None:
                kwargs['data'] = copied_data[node_index]

            response = self._try_do_request(*args, **kwargs)
            if response is _TRY_NEXT_NODE:
                continue
            return response

        raise CloudifyClientError('All cluster nodes are offline')

    def _try_do_request(self, *args, **kwargs):
        try:
            return super(ClusterHTTPClient, self).do_request(*args,
                                                             **kwargs)
        except (requests.exceptions.ConnectionError,
                CloudifyClientError) as e:
            if isinstance(e, CloudifyClientError) and e.status_code != 502:
                raise
            self.logger.warning('Could not connect to manager %s on port %s',
                                self.host, self.port)
            self.logger.debug(str(e))
        return _TRY_NEXT_NODE

    def _use_node(self, node):
        if ipv6_url_compat(node['host_ip']) == self.host:
            return
        self.host = ipv6_url_compat(node['host_ip'])
        for attr in ['rest_port', 'rest_protocol', 'trust_all', 'cert']:
            new_value = node.get(attr)
            if new_value:
                setattr(self, attr, new_value)
        self._update_profile(node)

    def _update_profile(self, node):
        """
        Put the node at the start of the cluster list in profile.

        The client tries nodes in the order of the cluster list, so putting
        the node first will make the client try it first next time. This makes
        the client always try the last-known-active-manager first.
        """
        self._profile.cluster[CloudifyNodeType.MANAGER].remove(node)
        self._profile.cluster[CloudifyNodeType.MANAGER] = (
            [node] + self._profile.cluster[CloudifyNodeType.MANAGER])
        for node_attr in CLUSTER_NODE_ATTRS:
            if node_attr in node:
                setattr(self._profile, node_attr, node[node_attr])
        self._profile.save()


class CloudifyClusterClient(CloudifyClient):
    """
    A CloudifyClient that will retry the queries with the current manager.

    When a request fails with a connection error, this will keep trying with
    every node in the cluster, until it finds an active manager.

    When an active manager is found, the profile will be updated with its
    address.
    """
    def __init__(self, profile, *args, **kwargs):
        self._profile = profile
        super(CloudifyClusterClient, self).__init__(*args, **kwargs)

    def client_class(self, *args, **kwargs):
        kwargs.setdefault('profile', self._profile)
        return ClusterHTTPClient(*args, **kwargs)


@contextmanager
def ssh_connection(host=None, user=None, key=None):
    if Connection is None:
        raise CloudifyCliError(
            "SSH not available - fabric not installed")
    if host is None:
        host = profile.manager_ip
    if user is None:
        user = profile.ssh_user
    if key is None:
        key = profile.ssh_key
    connect_kwargs = {}
    if key:
        connect_kwargs['key_filename'] = [key]
    conn = Connection(
        host=host,
        user=user,
        port=profile.ssh_port or 22,
        connect_kwargs=connect_kwargs or None
    )
    try:
        conn.open()
        yield conn
    except AuthenticationException as e:
        if user:
            user_message = user
        else:
            user_message = '{0} (from ssh config)'.format(conn.user)

        if key:
            key_message = key
        elif conn.ssh_config.get('identityfile'):
            key_message = '{0} (from ssh config)'.format(
                ', '.join(conn.ssh_config['identityfile']))
        else:
            key_message = 'default'

        raise CloudifyCliError(
            "SSH: could not connect to {host} "
            "(username: {user}, key: {key}): {exc}"
            .format(
                host=conn.host,
                user=user_message,
                key=key_message,
                exc=e
            )
        )
    finally:
        conn.close()


profile = get_profile_context(suppress_error=True)
target_manager = None
