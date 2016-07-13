########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import os
import sys
import json
import errno
import socket
import string
import random
import shutil
import pkgutil
import getpass
import tempfile
from contextlib import contextmanager

import yaml
import pkg_resources
from prettytable import PrettyTable
from itsdangerous import base64_encode
from jinja2.environment import Template

from dsl_parser import utils as dsl_parser_utils
from dsl_parser.constants import IMPORT_RESOLVER_KEY

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

import cloudify_cli
from . import constants
from .config import helptexts
from .exceptions import CloudifyCliError


DEFAULT_LOG_FILE = os.path.expanduser(
    '{0}/cloudify-{1}/cloudify-cli.log'
    .format(tempfile.gettempdir(),
            getpass.getuser()))


CLOUDIFY_WORKDIR = os.path.join(
    os.path.expanduser('~'),
    constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
CLOUDIFY_CONFIG_PATH = os.path.join(CLOUDIFY_WORKDIR, 'config.yaml')
PROFILES_DIR = os.path.join(CLOUDIFY_WORKDIR, 'profiles')
ACTIVE_PRO_FILE = os.path.join(CLOUDIFY_WORKDIR, 'active.profile')


def delete_profile(profile_name):
    profile_dir = os.path.join(PROFILES_DIR, profile_name)
    if os.path.isdir(profile_dir):
        shutil.rmtree(profile_dir)


def get_profile(profile_name):
    set_active_profile(profile_name)

    # TODO: add rest port and protocol, ssh port and ssh password
    cosmo_wd_settings = load_cloudify_working_dir_settings(profile_name)
    ssh_key_path = cosmo_wd_settings.get_management_key() or 'Not Set'
    ssh_user = cosmo_wd_settings.get_management_user() or 'Not Set'
    manager_ip = cosmo_wd_settings.get_management_server() or 'Not Set'

    return dict(
        manager_ip=manager_ip,
        alias=None,
        ssh_key_path=ssh_key_path,
        ssh_user=ssh_user)


def is_profile_exists(profile_name):
    return os.path.isfile(os.path.join(
        PROFILES_DIR, profile_name, 'context'))


def assert_profile_exists(profile_name=None):
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
        return None


def is_manager_active():
    active_profile = get_active_profile()
    if not active_profile:
        return False

    profile = load_cloudify_working_dir_settings(
        active_profile, suppress_error=True)
    if not (profile and profile.get_management_server()):
        return False
    return True


# TODO: default to `get_active_profile` if profile name is not provided
def load_cloudify_working_dir_settings(profile_name, suppress_error=False):
    try:
        path = get_context_path(profile_name)
        with open(path) as f:
            return yaml.load(f.read())
    except CloudifyCliError:
        if suppress_error:
            return None
        raise


def get_context_path(profile_name=None):
    profile_name = profile_name or get_active_profile()
    if not profile_name:
        raise CloudifyCliError(
            'No profile name provided and there is no '
            'currently active profile. Please initialize '
            'and try again.')
    init_path = get_init_path(profile_name)
    if init_path is None:
        raise_uninitialized()
    context_path = os.path.join(
        init_path,
        constants.CLOUDIFY_WD_SETTINGS_FILE_NAME)
    if not os.path.isfile(context_path):
        raise CloudifyCliError('File {0} does not exist'.format(context_path))
    return context_path


def is_initialized(profile_name=None):
    if profile_name:
        return get_init_path(profile_name) is not None
    else:
        return os.path.isfile(CLOUDIFY_CONFIG_PATH)


def get_init_path(profile_name):
    """
    Returns the path of the .cloudify dir

    search in each directory up the cwd directory tree for the existence of the
    Cloudify settings directory (`.cloudify`).
    :return: if we found it, return it's path. else, return None
    """
    path = os.path.join(PROFILES_DIR, profile_name)
    return path if os.path.isdir(path) else None


def dump_configuration_file():
    config = pkg_resources.resource_string(
        cloudify_cli.__name__,
        'resources/config.yaml')

    template = Template(config)
    rendered = template.render(log_path=DEFAULT_LOG_FILE)
    with open(CLOUDIFY_CONFIG_PATH, 'w') as f:
        f.write(rendered)
        f.write(os.linesep)


def dump_cloudify_working_dir_settings(cosmo_wd_settings=None,
                                       update=False,
                                       profile_name=None):
    workdir = os.path.join(PROFILES_DIR, profile_name)
    if cosmo_wd_settings is None:
        cosmo_wd_settings = CloudifyWorkingDirectorySettings()
    if update:
        # locate existing file
        # this will raise an error if the file doesn't exist.
        target_file_path = get_context_path(profile_name)
    else:

        # create a new file
        if not os.path.exists(workdir):
            os.mkdir(workdir)
        target_file_path = os.path.join(
            workdir,
            constants.CLOUDIFY_WD_SETTINGS_FILE_NAME)

    with open(target_file_path, 'w') as f:
        f.write(yaml.dump(cosmo_wd_settings))


def raise_uninitialized():
    error = CloudifyCliError(
        'Cloudify environment is not initalized')
    error.possible_solutions = [
        "Run 'cfy init'"
    ]
    raise error


@contextmanager
def profile(profile_name):
    profile = load_cloudify_working_dir_settings(profile_name)
    yield profile


@contextmanager
def update_wd_settings(profile_name):
    cosmo_wd_settings = load_cloudify_working_dir_settings(profile_name)
    yield cosmo_wd_settings
    dump_cloudify_working_dir_settings(
        cosmo_wd_settings,
        update=True,
        profile_name=profile_name)


def dump_to_file(collection, file_path):
    with open(file_path, 'a') as f:
        f.write(os.linesep.join(collection))
        f.write(os.linesep)


def is_virtual_env():
    return hasattr(sys, 'real_prefix')


def is_use_colors():
    if not is_initialized():
        return False

    config = CloudifyConfig()
    return config.colors


def is_auto_generate_ids():
    if not is_initialized():
        return False

    config = CloudifyConfig()
    return config.auto_generate_ids


def get_import_resolver():
    if not is_initialized():
        return None

    config = CloudifyConfig()
    # get the resolver configuration from the config file
    local_import_resolver = config.local_import_resolver
    return dsl_parser_utils.create_import_resolver(local_import_resolver)


def is_validate_definitions_version():
    if not is_initialized():
        return True
    config = CloudifyConfig()
    return config.validate_definitions_version


def get_cwd():
    """Allows use to patch the cwd when needed.
    """
    return os.getcwd()


def get_rest_client(manager_ip=None,
                    rest_port=None,
                    protocol=None,
                    skip_version_check=False):
    if not manager_ip:
        manager_ip = get_management_server_ip()

    if not rest_port:
        rest_port = get_rest_port()

    if not protocol:
        protocol = get_protocol()

    username = get_username()

    password = get_password()

    headers = get_auth_header(username, password)

    cert = get_ssl_cert()

    trust_all = get_ssl_trust_all()

    client = CloudifyClient(host=manager_ip, port=rest_port, protocol=protocol,
                            headers=headers, cert=cert, trust_all=trust_all)

    if skip_version_check:
        return client

    cli_version, manager_version = get_cli_manager_versions()

    if cli_version == manager_version:
        return client
    elif not manager_version:
        # TODO: log that: Version compatibility check could not be performed
        # the current problem is that there's a circular import between utils
        # and logger which we need to solve.
        return client
    else:
        message = ('CLI and manager versions do not match\n'
                   'CLI Version: {0}\n'
                   'Manager Version: {1}').format(cli_version, manager_version)
        raise CloudifyCliError(message)


def get_auth_header(username, password):
    header = None

    if username and password:
        credentials = '{0}:{1}'.format(username, password)
        header = {
            constants.CLOUDIFY_AUTHENTICATION_HEADER:
                constants.BASIC_AUTH_PREFIX + ' ' + base64_encode(credentials)}

    return header


def get_rest_port():
    active_profile = get_active_profile()
    cosmo_wd_settings = load_cloudify_working_dir_settings(active_profile)
    return cosmo_wd_settings.get_rest_port()


def get_protocol():
    active_profile = get_active_profile()
    cosmo_wd_settings = load_cloudify_working_dir_settings(active_profile)
    return cosmo_wd_settings.get_protocol()


def get_management_user():
    active_profile = get_active_profile()
    cosmo_wd_settings = load_cloudify_working_dir_settings(active_profile)
    if cosmo_wd_settings.get_management_user():
        return cosmo_wd_settings.get_management_user()
    msg = 'Management User is not set in working directory settings'
    raise CloudifyCliError(
        '{0}\n{1}'.format(msg, helptexts.SET_MANAGEMENT_CREDS))


def get_management_key():
    active_profile = get_active_profile()
    cosmo_wd_settings = load_cloudify_working_dir_settings(active_profile)
    if cosmo_wd_settings.get_management_key():
        return cosmo_wd_settings.get_management_key()
    msg = 'Management Key is not set in working directory settings'
    raise CloudifyCliError(
        '{0}\n{1}'.format(msg, helptexts.SET_MANAGEMENT_CREDS))


def get_management_server_ip():
    active_profile = get_active_profile()
    cosmo_wd_settings = load_cloudify_working_dir_settings(active_profile)
    management_ip = cosmo_wd_settings.get_management_server()
    if management_ip:
        return management_ip
    raise CloudifyCliError(
        "You must being using a manager to perform this action. "
        "You can run `cfy use MANAGER_IP` to use a manager.")


def get_username():
    return os.environ.get(constants.CLOUDIFY_USERNAME_ENV)


def get_password():
    return os.environ.get(constants.CLOUDIFY_PASSWORD_ENV)


def get_ssl_cert():
    return os.environ.get(constants.CLOUDIFY_SSL_CERT)


def get_ssl_trust_all():
    trust_all = os.environ.get(constants.CLOUDIFY_SSL_TRUST_ALL)
    if trust_all is not None and len(trust_all) > 0:
        return True
    return False


def decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = decode_list(item)
        elif isinstance(item, dict):
            item = decode_dict(item)
        rv.append(item)
    return rv


def decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = decode_list(value)
        elif isinstance(value, dict):
            value = decode_dict(value)
        rv[key] = value
    return rv


def print_workflows(workflows, deployment):
    pt = table(['blueprint_id', 'deployment_id',
                'name', 'created_at'],
               data=workflows,
               defaults={'blueprint_id': deployment.blueprint_id,
                         'deployment_id': deployment.id})
    print_table('Workflows:', pt)


def get_version():
    version_data = get_version_data()
    return version_data['version']


def get_version_data():
    data = pkgutil.get_data('cloudify_cli', 'VERSION')
    return json.loads(data)


def connected_to_manager(management_ip):
    port = get_rest_port()
    try:
        sock = socket.create_connection((str(management_ip), int(port)), 5)
        sock.close()
        return True
    except ValueError:
        return False
    except socket.error:
        return False


def get_manager_version_data():
    active_profile = get_active_profile()
    dir_settings = load_cloudify_working_dir_settings(
        active_profile, suppress_error=True)
    if not (dir_settings and dir_settings.get_management_server()):
        return None
    management_ip = dir_settings.get_management_server()
    if not connected_to_manager(management_ip):
        return None
    client = get_rest_client(management_ip, skip_version_check=True)
    try:
        version_data = client.manager.get_version()
    except CloudifyClientError:
        return None
    version_data['ip'] = management_ip
    return version_data


def get_cli_manager_versions():
    manager_version_data = get_manager_version_data()
    cli_version = get_version_data().get('version')

    if not manager_version_data:
        return cli_version, None
    else:
        manager_version = manager_version_data.get('version')
        return cli_version, manager_version


def table(cols, data, defaults=None):
    """
    Return a new PrettyTable instance representing the list.

    Arguments:

        cols - An iterable of strings that specify what
               are the columns of the table.

               for example: ['id','name']

        data - An iterable of dictionaries, each dictionary must
               have key's corresponding to the cols items.

               for example: [{'id':'123', 'name':'Pete']

        defaults - A dictionary specifying default values for
                   key's that don't exist in the data itself.

                   for example: {'deploymentId':'123'} will set the
                   deploymentId value for all rows to '123'.

    """

    pt = PrettyTable([col for col in cols])

    for d in data:
        pt.add_row(map(lambda c: d[c] if c in d else defaults[c], cols))

    return pt


class CloudifyWorkingDirectorySettings(yaml.YAMLObject):
    yaml_tag = u'!WD_Settings'
    yaml_loader = yaml.Loader

    def __init__(self):
        self._bootstrap_state = None
        self._management_ip = None
        self._management_key = None
        self._management_password = None
        self._management_port = None
        self._management_user = None
        self._provider_context = None
        self._rest_port = constants.DEFAULT_REST_PORT
        self._protocol = constants.DEFAULT_PROTOCOL

    def get_bootstrap_state(self):
        return self._bootstrap_state

    def set_bootstrap_state(self, bootstrap_state):
        self._bootstrap_state = bootstrap_state

    def get_management_server(self):
        return self._management_ip

    def set_management_server(self, management_ip):
        self._management_ip = management_ip

    def get_management_key(self):
        return self._management_key

    def set_management_key(self, management_key):
        self._management_key = management_key

    def get_management_password(self):
        return self._management_password

    def set_management_password(self, management_password):
        self._management_password = management_password

    def get_management_port(self):
        return self._management_port

    def set_management_port(self, management_port):
        self._management_port = management_port

    def get_management_user(self):
        return self._management_user

    def set_management_user(self, _management_user):
        self._management_user = _management_user

    def get_provider_context(self):
        return self._provider_context

    def set_provider_context(self, provider_context):
        self._provider_context = provider_context

    def remove_management_server_context(self):
        self._management_ip = None

    def get_rest_port(self):
        return self._rest_port

    def set_rest_port(self, rest_port):
        self._rest_port = rest_port

    def get_protocol(self):
        return self._protocol

    def set_protocol(self, protocol):
        self._protocol = protocol


def remove_if_exists(path):

    try:
        if os.path.isfile(path):
            os.remove(path)
        if os.path.isdir(path):
            shutil.rmtree(path)

    except OSError as e:
        if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
            raise  # re-raise exception if a different error occurred


def generate_random_string(size=6,
                           chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def delete_cloudify_working_dir_settings():
    target_file_path = os.path.join(
        os.path.expanduser('~'), constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
        constants.CLOUDIFY_WD_SETTINGS_FILE_NAME)
    if os.path.exists(target_file_path):
        os.remove(target_file_path)


class CloudifyConfig(object):

    class Logging(object):

        def __init__(self, logging):
            self._logging = logging or {}

        @property
        def filename(self):
            return self._logging.get('filename')

        @property
        def loggers(self):
            return self._logging.get('loggers', {})

    def __init__(self):
        with open(CLOUDIFY_CONFIG_PATH) as f:
            self._config = yaml.safe_load(f.read())

    @property
    def colors(self):
        return self._config.get('colors', False)

    @property
    def auto_generate_ids(self):
        return self._config.get('auto_generate_ids', False)

    @property
    def logging(self):
        return self.Logging(self._config.get('logging', {}))

    @property
    def local_provider_context(self):
        return self._config.get('local_provider_context', {})

    @property
    def local_import_resolver(self):
        return self._config.get(IMPORT_RESOLVER_KEY, {})

    @property
    def validate_definitions_version(self):
        return self._config.get('validate_definitions_version', True)


def build_manager_host_string(user='', ip=''):
    user = user or get_management_user()
    ip = ip or get_management_server_ip()
    return '{0}@{1}'.format(user, ip)


# TODO: apply to log messages if necessary or remove
def manager_msg(message, manager_ip=None):
    return '{0} [Manager={1}]'.format(
        message, manager_ip or get_management_server_ip())


def _generate_suffixed_id(id):
    return '{0}_{1}'.format(id, generate_random_string())
