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
import yaml

from dsl_parser import utils as dsl_parser_utils
from dsl_parser.constants import IMPORT_RESOLVER_KEY
from dsl_parser.import_resolver.default_import_resolver import (
    DefaultImportResolver
)

from .. import env, exceptions


CLOUDIFY_CONFIG_PATH = os.path.join(env.CLOUDIFY_WORKDIR, 'config.yaml')


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


def is_use_colors():
    if not env.is_initialized():
        return False

    config = CloudifyConfig()
    return config.colors


def is_auto_generate_ids():
    if not env.is_initialized():
        return False

    config = CloudifyConfig()
    return config.auto_generate_ids


def get_import_resolver():
    local_import_resolver = {
        'implementation': 'cloudify_cli.config.config:ResolverWithPlugins'
    }
    if env.is_initialized():
        config = CloudifyConfig()
        # get the resolver configuration from the config file
        if isinstance(config.local_import_resolver, dict):
            local_import_resolver.update(config.local_import_resolver)
    return dsl_parser_utils.create_import_resolver(local_import_resolver)


def is_validate_definitions_version():
    if not env.is_initialized():
        return True
    config = CloudifyConfig()
    return config.validate_definitions_version


class ResolverWithPlugins(DefaultImportResolver):
    PREFIX = 'plugin:'

    def fetch_import(self, import_url):
        if self._is_plugin_url(import_url):
            e = exceptions.CloudifyCliError(
                'Error fetching plugin yaml: {0!r}\nBlueprints using plugin '
                'repository imports can not be validated locally.'
                .format(import_url))
            e.possible_solutions = [
                'Upload the blueprint to a Cloudify Manager',
                'Use an explicit URL to the plugin YAML file instead of a '
                'plugin repository `plugin:` import'
            ]
            raise e
        return super(ResolverWithPlugins, self).fetch_import(import_url)

    def _is_plugin_url(self, import_url):
        return import_url.startswith(self.PREFIX)
