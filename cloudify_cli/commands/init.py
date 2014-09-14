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

"""
Handles 'cfy init'
"""

import shutil
import yaml

from fabric.operations import local
from fabric.operations import os
from cloudify_cli import utils
from os.path import dirname
from cloudify_cli.constants import CONFIG_FILE_NAME
from cloudify_cli.constants import DEFAULTS_CONFIG_FILE_NAME
from cloudify_cli.constants import CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME
from cloudify_cli.constants import CLOUDIFY_WD_SETTINGS_FILE_NAME
from cloudify_cli.logger import lgr
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.utils import CloudifyWorkingDirectorySettings
from cloudify_cli.utils import get_provider_module
from cloudify_cli.utils import get_cwd
from cloudify_cli.utils import dump_cloudify_working_dir_settings


def _init(provider, reset_config, install=False,
          creds=None):

    """
    initializes a provider by copying its config files to the cwd.
    First, will look for a module named cloudify_#provider#.
    If not found, will look for #provider#.
    If install is True, will install the supplied provider and perform
    the search again.

    :param string provider: the provider's name
    :param bool reset_config: if True, overrides the current config.
    :param bool install: if supplied, will also install the desired
     provider according to the given url or module name (pypi).
    :param creds: a comma separated key=value list of credential info.
     this is specific to each provider.
    :rtype: `string` representing the provider's module name
    """
    def _get_provider_by_name():
        try:
            # searching first for the standard name for providers
            # (i.e. cloudify_XXX)
            provider_module_name = 'cloudify_{0}'.format(provider)
            # print provider_module_name
            return (provider_module_name,
                    get_provider_module(provider_module_name))
        except CloudifyCliError:
            # if provider was not found, search for the exact literal the
            # user requested instead
            provider_module_name = provider
            return (provider_module_name,
                    get_provider_module(provider_module_name))

    try:
        provider_module_name, provider = _get_provider_by_name()
    except:
        if install:
            local('pip install {0} --process-dependency-links'
                  .format(install))
        provider_module_name, provider = _get_provider_by_name()

    target_file = os.path.join(utils.get_cwd(), CONFIG_FILE_NAME)
    if not reset_config and os.path.exists(target_file):
        msg = ('Target directory {0} already contains a '
               'provider configuration file; '
               'use the "-r" flag to '
               'reset it back to its default values.'
               .format(dirname(target_file)))
        raise CloudifyCliError(msg)
    else:
        # try to get the path if the provider is a module
        try:
            provider_dir = provider.__path__[0]
        # if not, assume it's in the package's dir
        except:
            provider_dir = os.path.dirname(provider.__file__)
        files_path = os.path.join(provider_dir, CONFIG_FILE_NAME)
        lgr.debug('Copying provider files from {0} to {1}'
                  .format(files_path, get_cwd()))
        shutil.copy(files_path, get_cwd())

    if creds:
        src_config_file = '{}/{}'.format(provider_dir,
                                         DEFAULTS_CONFIG_FILE_NAME)
        dst_config_file = '{}/{}'.format(get_cwd(),
                                         CONFIG_FILE_NAME)
        with open(src_config_file, 'r') as f:
            provider_config = yaml.load(f.read())
            # print provider_config
            # TODO: handle cases in which creds might contain ',' or '='
            if 'credentials' in provider_config.keys():
                for cred in creds.split(','):
                    key, value = cred.split('=')
                    if key in provider_config['credentials'].keys():
                        provider_config['credentials'][key] = value
                    else:
                        lgr.error('could not find key "{0}" in config file'
                                  .format(key))
                        raise CloudifyCliError('key not found')
            else:
                lgr.error('credentials section not found in config')
        # print yaml.dump(provider_config)
        with open(dst_config_file, 'w') as f:
            f.write(yaml.dump(provider_config, default_flow_style=False))

    return provider_module_name


def init(provider, reset_config, creds, install):

    if os.path.exists(os.path.join(get_cwd(),
                                   CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
                                   CLOUDIFY_WD_SETTINGS_FILE_NAME)):
        if not reset_config:
            msg = ('Current directory is already initialized. '
                   'Use the "-r" flag to force '
                   'reinitialization (might overwrite '
                   'provider configuration files if exist).')
            raise CloudifyCliError(msg)

        else:  # resetting provider configuration
            lgr.debug('resetting configuration...')
            _init(provider,
                  reset_config,
                  creds=creds)
            lgr.info("Configuration reset complete")
            return

    lgr.info("Initializing Cloudify")
    provider_module_name = _init(provider,
                                 reset_config,
                                 install,
                                 creds)

    settings = CloudifyWorkingDirectorySettings()
    settings.set_provider(provider_module_name)

    dump_cloudify_working_dir_settings(settings)

    lgr.info("Initialization complete")
