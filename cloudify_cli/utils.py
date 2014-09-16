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

import json
import os
import imp
import pkgutil
import sys
import yaml

from contextlib import contextmanager
from copy import deepcopy
from prettytable import PrettyTable
from cloudify_cli.logger import lgr
from cloudify_cli.logger import flgr
from cloudify_rest_client import CloudifyClient
from cloudify_cli.constants import REST_PORT
from cloudify_cli.constants import CLOUDIFY_WD_SETTINGS_FILE_NAME
from cloudify_cli.constants import CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME
from cloudify_cli.constants import CONFIG_FILE_NAME
from cloudify_cli.constants import DEFAULTS_CONFIG_FILE_NAME
from cloudify_cli.exceptions import CloudifyCliError


class ProviderConfig(dict):

    @property
    def resources_prefix(self):
        return self.get('cloudify', {}).get('resources_prefix', '')


def get_management_user():
    cosmo_wd_settings = load_cloudify_working_dir_settings()
    if cosmo_wd_settings.get_management_user():
        return cosmo_wd_settings.get_management_user()
    msg = 'Management User is not set in working directory settings'
    raise CloudifyCliError(msg)


def load_cloudify_working_dir_settings(suppress_error=False):
    try:
        path = get_context_path()
        with open(path, 'r') as f:
            return yaml.load(f.read())
    except CloudifyCliError as e:
        if suppress_error:
            return None
        msg = ('You must first initialize by running the '
               'command "cfy init", or choose to work with '
               'an existing management server by running the '
               'command "cfy use".')
        full_message = '{0}. {1}'.format(e.message, msg)
        raise CloudifyCliError(full_message)


def get_management_key():
    cosmo_wd_settings = load_cloudify_working_dir_settings()
    if cosmo_wd_settings.get_management_key():
        return cosmo_wd_settings.get_management_key()
    msg = 'Management Key is not set in working directory settings'
    raise CloudifyCliError(msg)


def get_context_path():
    context_path = os.path.join(get_init_path(),
                                CLOUDIFY_WD_SETTINGS_FILE_NAME)
    if not os.path.exists(context_path):
        raise CloudifyCliError('File {0} does not exist'
                               .format(context_path))
    return context_path


def json_to_dict(json_resource, json_resource_name):
    if not json_resource:
        return None
    try:
        if os.path.exists(json_resource):
            with open(json_resource, 'r') as f:
                return json.loads(f.read())
        else:
            return json.loads(json_resource)
    except ValueError, e:
        msg = ("'{0}' must be a valid JSON. {1}"
               .format(json_resource_name, str(e)))
        raise CloudifyCliError(msg)


def get_init_path():

    flgr.debug('Looking up {0}'.format(CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME))
    current_lookup_dir = get_cwd()

    found = False
    while not found:

        path = os.path.join(current_lookup_dir,
                            CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)

        if os.path.exists(path):
            return path
        else:
            flgr.debug('{0} not found in {1}'
                       .format(CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
                               current_lookup_dir))
            if os.path.dirname(current_lookup_dir) == current_lookup_dir:
                raise CloudifyCliError(
                    'Cannot find {0} in {1}, '
                    'or in any of its parent directories'
                    .format(CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
                            get_cwd()))
            current_lookup_dir = os.path.dirname(current_lookup_dir)


def dump_cloudify_working_dir_settings(cosmo_wd_settings, update=False):

    if update:
        # locate existing file
        # this will raise an error if the file doesnt exist.
        target_file_path = get_context_path()
    else:

        # create a new file
        path = os.path.join(get_cwd(),
                            CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
        flgr.debug('Creating {0} in {1}'
                   .format(CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
                           get_cwd()))
        if not os.path.exists(path):
            os.mkdir(path)
        target_file_path = os.path.join(get_cwd(),
                                        CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
                                        CLOUDIFY_WD_SETTINGS_FILE_NAME)

    with open(target_file_path, 'w') as f:
        flgr.debug('Writing context to {0}'
                   .format(target_file_path))
        f.write(yaml.dump(cosmo_wd_settings))


@contextmanager
def update_wd_settings():
    cosmo_wd_settings = load_cloudify_working_dir_settings()
    yield cosmo_wd_settings
    dump_cloudify_working_dir_settings(cosmo_wd_settings, update=True)


def get_cwd():
    return os.getcwd()


def get_rest_client(manager_ip, rest_port=REST_PORT):
    return CloudifyClient(manager_ip, rest_port)


def get_management_server_ip():

    cosmo_wd_settings = load_cloudify_working_dir_settings()
    management_ip = cosmo_wd_settings.get_management_server()
    if management_ip:
        return management_ip

    msg = ("Must either first run 'cfy use' command for a "
           "management server or provide a management "
           "server ip explicitly")
    raise CloudifyCliError(msg)


def print_table(title, tb):
    lgr.info('{0}{1}{0}{2}{0}'.format(os.linesep, title, tb))


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


def get_provider():
    cosmo_wd_settings = load_cloudify_working_dir_settings()
    if cosmo_wd_settings.get_provider():
        return cosmo_wd_settings.get_provider()
    msg = 'Provider is not set in working directory settings'
    raise RuntimeError(msg)


def get_provider_module(provider_name):
    try:
        module_or_pkg_desc = imp.find_module(provider_name)
        if not module_or_pkg_desc[1]:
            # module_or_pkg_desc[1] is the pathname of found module/package,
            # if it's empty none were found
            msg = ('Provider {0} not found.'.format(provider_name))
            raise CloudifyCliError(msg)

        module = imp.load_module(provider_name, *module_or_pkg_desc)

        if not module_or_pkg_desc[0]:
            # module_or_pkg_desc[0] is None and module_or_pkg_desc[1] is not
            # empty only when we've loaded a package rather than a module.
            # Re-searching for the module inside the now-loaded package
            # with the same name.
            module = imp.load_module(
                provider_name,
                *imp.find_module(provider_name, module.__path__))
        return module
    except ImportError:
        msg = ('Could not import module {0}. '
               'maybe {0} provider module was not installed?'
               .format(provider_name))
        raise CloudifyCliError(msg)


def read_config(config_file_path, provider_dir):

    def _deep_merge_dictionaries(overriding_dict, overridden_dict):
        merged_dict = deepcopy(overridden_dict)
        for k, v in overriding_dict.iteritems():
            if k in merged_dict and isinstance(v, dict):
                if isinstance(merged_dict[k], dict):
                    merged_dict[k] = \
                        _deep_merge_dictionaries(v, merged_dict[k])
                else:
                    raise RuntimeError('type conflict at key {0}'.format(k))
            else:
                merged_dict[k] = deepcopy(v)
        return merged_dict

    if not config_file_path:
        config_file_path = CONFIG_FILE_NAME
    defaults_config_file_path = os.path.join(
        provider_dir,
        DEFAULTS_CONFIG_FILE_NAME)

    config_file_path = os.path.join(get_cwd(), config_file_path)
    if not os.path.exists(config_file_path) or not os.path.exists(
            defaults_config_file_path):
        if not os.path.exists(defaults_config_file_path):
            raise ValueError('Defaults configuration file missing; '
                             'expected to find it at {0}'
                             .format(defaults_config_file_path))
        raise ValueError('Configuration file missing; expected to find '
                         'it at {0}'.format(config_file_path))

    lgr.debug('reading provider config files')
    with open(config_file_path, 'r') as config_file, \
            open(defaults_config_file_path, 'r') as defaults_config_file:

        lgr.debug('safe loading user config')
        user_config = yaml.safe_load(config_file.read())

        lgr.debug('safe loading default config')
        defaults_config = yaml.safe_load(defaults_config_file.read())

    lgr.debug('merging configs')
    merged_config = _deep_merge_dictionaries(user_config, defaults_config) \
        if user_config else defaults_config
    return ProviderConfig(merged_config)


@contextmanager
def protected_provider_call():
    try:
        yield
    except Exception, ex:
        trace = sys.exc_info()[2]
        msg = 'Exception occurred in provider: {0}'.format(str(ex))
        raise CloudifyCliError(msg), None, trace


def get_version():
    version_data = get_version_data()
    return version_data['version']


def get_version_data():
    data = pkgutil.get_data('cloudify_cli.resources', 'VERSION')
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
        self._provider = None
        self._provider_context = None
        self._mgmt_aliases = {}

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

    def get_provider(self):
        return self._provider

    def set_provider(self, provider):
        self._provider = provider


def delete_cloudify_working_dir_settings():
    target_file_path = os.path.join(get_cwd(),
                                    CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
                                    CLOUDIFY_WD_SETTINGS_FILE_NAME)
    if os.path.exists(target_file_path):
        os.remove(target_file_path)
