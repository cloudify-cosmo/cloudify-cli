import os
import json
import socket
import shutil
import pkgutil
import getpass
import tempfile

import yaml
import pkg_resources
from itsdangerous import base64_encode
from jinja2.environment import Template

from dsl_parser import utils as dsl_parser_utils
from dsl_parser.constants import IMPORT_RESOLVER_KEY

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

import cloudify_cli
from . import constants
from .exceptions import CloudifyCliError


DEFAULT_LOG_FILE = os.path.expanduser(
    '{0}/cloudify-{1}/cloudify-cli.log'.format(
        tempfile.gettempdir(), getpass.getuser()))

CLOUDIFY_WORKDIR = os.path.join(
    os.environ.get('CFY_WORKDIR', os.path.expanduser('~')),
    constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
CLOUDIFY_CONFIG_PATH = os.path.join(CLOUDIFY_WORKDIR, 'config.yaml')
PROFILES_DIR = os.path.join(CLOUDIFY_WORKDIR, 'profiles')
ACTIVE_PRO_FILE = os.path.join(CLOUDIFY_WORKDIR, 'active.profile')

_local_settings = None


def delete_profile(profile_name):
    profile_dir = os.path.join(PROFILES_DIR, profile_name)
    if os.path.isdir(profile_dir):
        shutil.rmtree(profile_dir)
    else:
        raise CloudifyCliError(
            'Profile {0} does not exist'.format(profile_name))


# TODO: Consider moving to profiles.py
def get_profile(profile_name):
    current_profile = get_active_profile()
    set_active_profile(profile_name)

    # TODO: add rest port and protocol, ssh port and ssh password
    context = get_profile_context(profile_name)
    manager_ip = context.get_manager_ip() or 'Not Set'
    ssh_key_path = context.get_manager_key() or 'Not Set'
    ssh_user = context.get_manager_user() or 'Not Set'
    ssh_port = context.get_manager_port() or 'Not Set'
    rest_port = context.get_rest_port() or 'Not Set'
    rest_protocol = context.get_rest_protocol() or 'Not Set'

    set_active_profile(current_profile)

    return dict(
        manager_ip=manager_ip,
        alias=None,
        ssh_key_path=ssh_key_path,
        ssh_user=ssh_user,
        ssh_port=ssh_port,
        rest_port=rest_port,
        rest_protocol=rest_protocol)


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
        # TODO: Don't quite understand this. If the active profile
        # file doesn't exist.. something fundemental is broken.
        return ''


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

    profile = get_profile_context(active_profile, suppress_error=True)
    if not (profile and profile.get_manager_ip()):
        return False
    return True


def get_profile_context(profile_name=None, suppress_error=False):
    profile_name = profile_name or get_active_profile()
    if profile_name == 'local':
        return None
    try:
        path = get_context_path(profile_name)
        with open(path) as f:
            return yaml.load(f.read())
    except CloudifyCliError:
        if suppress_error:
            return None
        raise


def is_initialized(profile_name=None):
    """Checks if a profile or an environment is initialized.

    If profile_name is provided, it will check if the profile
    is initialzed. If not, it will just check that the `local`
    profile is.
    """
    if profile_name:
        return get_init_path(profile_name) is not None
    else:
        return os.path.isfile(CLOUDIFY_CONFIG_PATH)


def get_context_path(profile_name=None):
    profile_name = profile_name or get_active_profile()
    if profile_name == 'local':
        raise CloudifyCliError('Local profile does not contain context')
    init_path = get_init_path(profile_name)
    context_path = os.path.join(
        init_path,
        constants.CLOUDIFY_WD_SETTINGS_FILE_NAME)
    return context_path


# TODO: Change name to get_profile_dir
def get_init_path(profile_name=None):
    active_profile = profile_name or get_active_profile()
    if active_profile and os.path.isdir(
            os.path.join(PROFILES_DIR, active_profile)):
        return os.path.join(PROFILES_DIR, active_profile)
    else:
        raise CloudifyCliError('Profile directory does not exist')


def set_cfy_config():
    config = pkg_resources.resource_string(
        cloudify_cli.__name__,
        'resources/config.yaml')

    template = Template(config)
    rendered = template.render(log_path=DEFAULT_LOG_FILE)
    with open(CLOUDIFY_CONFIG_PATH, 'w') as f:
        f.write(rendered)
        f.write(os.linesep)


def raise_uninitialized():
    error = CloudifyCliError(
        'Cloudify environment is not initalized')
    error.possible_solutions = [
        "Run 'cfy init'"
    ]
    raise error


def set_profile_context(context=None,
                        update=False,
                        profile_name=None):
    profile_name = profile_name or get_active_profile()
    if not profile_name or profile_name == 'local':
        raise CloudifyCliError(
            'Either provide a profile name or activate a profile')

    workdir = os.path.join(PROFILES_DIR, profile_name)
    if context is None:
        context = ProfileContext()
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
        f.write(yaml.dump(context))


def update_profile_context(manager_ip,
                           ssh_key_path=None,
                           ssh_password=None,
                           ssh_user=None,
                           ssh_port='22',
                           rest_port='80',
                           rest_protocol='http',
                           provider_context=None,
                           bootstrap_state=None,
                           alias=None):

    set_active_profile(manager_ip)
    provider_context = provider_context or {}
    settings = ProfileContext()

    settings.set_manager_ip(manager_ip)
    settings.set_manager_key(ssh_key_path)
    settings.set_manager_password(ssh_password)
    settings.set_manager_user(ssh_user)
    settings.set_manager_port(ssh_port)
    settings.set_rest_port(rest_port)
    settings.set_rest_protocol(rest_protocol)
    # TODO: add ssh port and password
    settings.set_provider_context(provider_context)
    settings.set_bootstrap_state(bootstrap_state)

    set_profile_context(
        profile_name=manager_ip,
        context=settings,
        update=False)


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


def get_rest_client(rest_host=None,
                    rest_port=None,
                    rest_protocol=None,
                    username=None,
                    password=None,
                    trust_all=False,
                    skip_version_check=False):
    # TODO: Go through all commands remove remove the call
    # to get_manager_ip_ip as it is already defaulted
    # here.
    rest_host = rest_host or get_rest_host()
    rest_port = rest_port or get_rest_port()
    rest_protocol = rest_protocol or get_rest_protocol()
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

    if skip_version_check or True:
        return client

    cli_version, manager_version = get_cli_manager_versions(client)

    if cli_version == manager_version:
        return client
    elif not manager_version:
        # TODO: log that: Version compatibility check could not be performed
        # the current problem is that there's a circular import between utils
        # and logger which we need to solve.
        return client
    else:
        raise CloudifyCliError(
            'CLI and manager versions do not match\n'
            'CLI Version: {0}\n'
            'Manager Version: {1}'.format(cli_version, manager_version))


def get_rest_port():
    context = get_profile_context()
    return context.get_rest_port()


def get_rest_protocol():
    context = get_profile_context()
    return context.get_rest_protocol()


# TODO: Replace all `manager` with `manager` for consistency
def get_manager_user():
    context = get_profile_context()
    if context.get_manager_user():
        return context.get_manager_user()
    raise CloudifyCliError(
        'Management User is not set in working directory settings')


def get_manager_port():
    context = get_profile_context()
    if context.get_manager_port():
        return context.get_manager_port()
    raise CloudifyCliError(
        'Management Port is not set in working directory settings')


def get_manager_key():
    context = get_profile_context()
    if context.get_manager_key():
        return context.get_manager_key()
    raise CloudifyCliError(
        'Management Key is not set in working directory settings')


def get_rest_host():
    context = get_profile_context()
    manager_ip = context.get_manager_ip()
    if manager_ip:
        return manager_ip
    raise CloudifyCliError(
        "You must being using a manager to perform this action. "
        "You can run `cfy use MANAGER_IP` to use a manager.")


def build_manager_host_string(user='', ip=''):
    user = user or get_manager_user()
    ip = ip or get_rest_host()
    return '{0}@{1}'.format(user, ip)


# TODO: apply to log messages if necessary or remove
def manager_msg(message, manager_ip=None):
    return '{0} [Manager={1}]'.format(
        message, manager_ip or get_rest_host())


def get_username():
    return os.environ.get(constants.CLOUDIFY_USERNAME_ENV)


def get_password():
    return os.environ.get(constants.CLOUDIFY_PASSWORD_ENV)


def get_default_rest_cert_local_path():
    return os.path.join(get_init_path(), constants.PUBLIC_REST_CERT)


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


# TODO: Check if this is at all used
def connected_to_manager(manager_ip):
    port = get_rest_port()
    try:
        sock = socket.create_connection((str(manager_ip), int(port)), 5)
        sock.close()
        return True
    except ValueError:
        return False
    except socket.error:
        return False


def get_manager_version_data(rest_client=None):
    if not rest_client:
        context = get_profile_context(suppress_error=True)
        if not (context and context.get_manager_ip()):
            return None
        manager_ip = context.get_manager_ip()
        if not connected_to_manager(manager_ip):
            return None
        rest_client = get_rest_client(manager_ip, skip_version_check=True)

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
    yaml_tag = u'!WD_Settings'
    yaml_loader = yaml.Loader

    def __init__(self):
        self._bootstrap_state = None
        self._manager_host = None
        self._manager_key = None
        self._manager_password = None
        self._manager_port = None
        self._manager_user = None
        self._provider_context = None
        self._rest_port = constants.DEFAULT_REST_PORT
        self._rest_protocol = constants.DEFAULT_REST_PROTOCOL

    def get_bootstrap_state(self):
        return self._bootstrap_state

    def set_bootstrap_state(self, bootstrap_state):
        self._bootstrap_state = bootstrap_state

    def get_manager_ip(self):
        return self._manager_host

    def set_manager_ip(self, manager_host):
        self._manager_host = manager_host

    def get_manager_key(self):
        return self._manager_key

    def set_manager_key(self, manager_key):
        self._manager_key = manager_key

    def get_manager_password(self):
        return self._manager_password

    def set_manager_password(self, manager_password):
        self._manager_password = manager_password

    def get_manager_port(self):
        return self._manager_port

    def set_manager_port(self, manager_port):
        self._manager_port = manager_port

    def get_manager_user(self):
        return self._manager_user

    def set_manager_user(self, _manager_user):
        self._manager_user = _manager_user

    def get_provider_context(self):
        return self._provider_context

    def set_provider_context(self, provider_context):
        self._provider_context = provider_context

    def remove_manager_server_context(self):
        self._manager_host = None

    def get_rest_port(self):
        return self._rest_port

    def set_rest_port(self, rest_port):
        self._rest_port = rest_port

    def get_rest_protocol(self):
        return self._rest_protocol

    def set_rest_protocol(self, rest_protocol):
        self._rest_protocol = rest_protocol


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


def get_auth_header(username, password):
    header = None

    if username and password:
        credentials = '{0}:{1}'.format(username, password)
        header = {
            constants.CLOUDIFY_AUTHENTICATION_HEADER:
                constants.BASIC_AUTH_PREFIX + ' ' + base64_encode(credentials)}

    return header
