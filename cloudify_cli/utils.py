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

import json
import os
import pkgutil
import sys
import tempfile
import getpass
from contextlib import contextmanager

import yaml
import pkg_resources
from jinja2.environment import Template
from prettytable import PrettyTable
from itsdangerous import base64_encode

from cloudify_rest_client import CloudifyClient

import cloudify_cli
from cloudify_cli import constants
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.logger import get_logger
from dsl_parser import utils as dsl_parser_utils
from dsl_parser.constants import IMPORT_RESOLVER_KEY

DEFAULT_LOG_FILE = os.path.expanduser(
    '{0}/cloudify-{1}/cloudify-cli.log'
    .format(tempfile.gettempdir(),
            getpass.getuser()))


def get_management_user():
    cosmo_wd_settings = load_cloudify_working_dir_settings()
    if cosmo_wd_settings.get_management_user():
        return cosmo_wd_settings.get_management_user()
    msg = 'Management User is not set in working directory settings'
    raise CloudifyCliError(msg)


def dump_to_file(collection, file_path):
    with open(file_path, 'a') as f:
        f.write(os.linesep.join(collection))
        f.write(os.linesep)


def is_virtual_env():
    return hasattr(sys, 'real_prefix')


def load_cloudify_working_dir_settings(suppress_error=False):
    try:
        path = get_context_path()
        with open(path, 'r') as f:
            return yaml.load(f.read())
    except CloudifyCliError:
        if suppress_error:
            return None
        raise


def get_management_key():
    cosmo_wd_settings = load_cloudify_working_dir_settings()
    if cosmo_wd_settings.get_management_key():
        return cosmo_wd_settings.get_management_key()
    msg = 'Management Key is not set in working directory settings'
    raise CloudifyCliError(msg)


def raise_uninitialized():
    error = CloudifyCliError(
        'Not initialized: Cannot find {0} in {1}, '
        'or in any of its parent directories'
        .format(constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
                get_cwd()))
    error.possible_solutions = [
        "Run 'cfy init' in this directory"
    ]
    raise error


def get_context_path():
    init_path = get_init_path()
    if init_path is None:
        raise_uninitialized()
    context_path = os.path.join(
        init_path,
        constants.CLOUDIFY_WD_SETTINGS_FILE_NAME
    )
    if not os.path.exists(context_path):
        raise CloudifyCliError(
            'File {0} does not exist'
            .format(context_path)
        )
    return context_path


def inputs_to_dict(resource, resource_name):
    if not resource:
        return None
    try:
        # parse resource as string representation of a dictionary
        parsed_dict = plain_string_to_dict(resource)
    except CloudifyCliError:
        try:
            # if resource is a path - parse as a yaml file
            if os.path.exists(resource):
                with open(resource, 'r') as f:
                    parsed_dict = yaml.load(f.read())
            else:
                # parse resource content as yaml
                parsed_dict = yaml.load(resource)
        except yaml.error.YAMLError as e:
            msg = ("'{0}' is not a valid YAML. {1}"
                   .format(resource_name, str(e)))
            raise CloudifyCliError(msg)

    if isinstance(parsed_dict, dict):
        return parsed_dict
    else:
        msg = "Invalid input: {0}. {1} must represent a dictionary. Valid " \
              "values can either be a path to a YAML file, a string " \
              "formatted as YAML or a string formatted as " \
              "key1=value1;key2=value2" \
            .format(resource, resource_name)
        raise CloudifyCliError(msg)


def plain_string_to_dict(input_string):
    input_string = input_string.strip()
    input_dict = {}
    mapped_inputs = input_string.split(';')
    for mapped_input in mapped_inputs:
        mapped_input = mapped_input.strip()
        if not mapped_input:
            continue
        split_mapping = mapped_input.split('=')
        if len(split_mapping) == 2:
            key = split_mapping[0].strip()
            value = split_mapping[1].strip()
            input_dict[key] = value
        else:
            msg = "Invalid input format: {0}, the expected format is: " \
                  "key1=value1;key2=value2".format(input_string)
            raise CloudifyCliError(msg)

    return input_dict


def is_initialized():
    return get_init_path() is not None


def get_init_path():
    current_lookup_dir = get_cwd()
    while True:

        path = os.path.join(current_lookup_dir,
                            constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)

        if os.path.exists(path):
            return path
        else:
            if os.path.dirname(current_lookup_dir) == current_lookup_dir:
                return None
            current_lookup_dir = os.path.dirname(current_lookup_dir)


def get_configuration_path():
    dot_cloudify = get_init_path()
    return os.path.join(
        dot_cloudify,
        'config.yaml'
    )


def dump_configuration_file():
    config = pkg_resources.resource_string(
        cloudify_cli.__name__,
        'resources/config.yaml')

    template = Template(config)
    rendered = template.render(log_path=DEFAULT_LOG_FILE)
    target_config_path = get_configuration_path()
    with open(os.path.join(target_config_path), 'w') as f:
        f.write(rendered)
        f.write(os.linesep)


def dump_cloudify_working_dir_settings(cosmo_wd_settings=None, update=False):
    if cosmo_wd_settings is None:
        cosmo_wd_settings = CloudifyWorkingDirectorySettings()
    if update:
        # locate existing file
        # this will raise an error if the file doesnt exist.
        target_file_path = get_context_path()
    else:

        # create a new file
        path = os.path.join(get_cwd(),
                            constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
        if not os.path.exists(path):
            os.mkdir(path)
        target_file_path = os.path.join(
            get_cwd(), constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
            constants.CLOUDIFY_WD_SETTINGS_FILE_NAME)

    with open(target_file_path, 'w') as f:
        f.write(yaml.dump(cosmo_wd_settings))


def is_use_colors():
    if not is_initialized():
        return False

    config = CloudifyConfig()
    return config.colors


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


@contextmanager
def update_wd_settings():
    cosmo_wd_settings = load_cloudify_working_dir_settings()
    yield cosmo_wd_settings
    dump_cloudify_working_dir_settings(cosmo_wd_settings, update=True)


def get_cwd():
    return os.getcwd()


def get_rest_client(manager_ip=None, rest_port=None, protocol=None):
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

    return CloudifyClient(host=manager_ip, port=rest_port, protocol=protocol,
                          headers=headers, cert=cert, trust_all=trust_all)


def get_auth_header(username, password):
    header = None

    if username and password:
        credentials = '{0}:{1}'.format(username, password)
        header = {
            constants.CLOUDIFY_AUTHENTICATION_HEADER:
                constants.BASIC_AUTH_PREFIX + ' ' + base64_encode(credentials)}

    return header


def get_rest_port():
    cosmo_wd_settings = load_cloudify_working_dir_settings()
    return cosmo_wd_settings.get_rest_port()


def get_protocol():
    cosmo_wd_settings = load_cloudify_working_dir_settings()
    return cosmo_wd_settings.get_protocol()


def get_management_server_ip():
    cosmo_wd_settings = load_cloudify_working_dir_settings()
    management_ip = cosmo_wd_settings.get_management_server()
    if management_ip:
        return management_ip

    msg = ("Must either first run 'cfy use' command for a "
           "management server or provide a management "
           "server ip explicitly")
    raise CloudifyCliError(msg)


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


def print_table(title, tb):
    get_logger().info('{0}{1}{0}{2}{0}'.format(os.linesep, title, tb))


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
        self._management_ip = None
        self._management_key = None
        self._management_user = None
        self._provider_context = None
        self._rest_port = constants.DEFAULT_REST_PORT
        self._protocol = constants.DEFAULT_PROTOCOL

    def get_management_server(self):
        return self._management_ip

    def set_management_server(self, management_ip):
        self._management_ip = management_ip

    def get_management_key(self):
        return self._management_key

    def set_management_key(self, management_key):
        self._management_key = management_key

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


def delete_cloudify_working_dir_settings():
    target_file_path = os.path.join(
        get_cwd(), constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
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
        with open(get_configuration_path()) as f:
            self._config = yaml.safe_load(f.read())

    @property
    def colors(self):
        return self._config.get('colors', False)

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
