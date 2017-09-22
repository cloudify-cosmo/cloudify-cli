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
import sys
import tempfile

from cloudify.workflows import local
from cloudify.utils import LocalCommandRunner

from dsl_parser.parser import parse_from_path
from dsl_parser import constants as dsl_constants

from . import env
from . import utils
from . import constants
from . import exceptions
from .logger import get_logger
from .config.config import CloudifyConfig


_ENV_NAME = 'local'


def initialize_blueprint(blueprint_path,
                         name,
                         storage=None,
                         install_plugins=False,
                         inputs=None,
                         resolver=None):
    logger = get_logger()

    logger.info('Initializing blueprint...')
    if install_plugins:
        _install_plugins(blueprint_path=blueprint_path)

    config = CloudifyConfig()
    return local.init_env(
        blueprint_path=blueprint_path,
        name=name,
        inputs=inputs,
        storage=storage,
        ignored_modules=constants.IGNORED_LOCAL_WORKFLOW_MODULES,
        provider_context=config.local_provider_context,
        resolver=resolver,
        validate_version=config.validate_definitions_version)


def storage_dir(blueprint_id=None):
    if blueprint_id:
        return os.path.join(
            env.PROFILES_DIR,
            _ENV_NAME,
            blueprint_id
        )
    else:
        directories = [env.PROFILES_DIR, _ENV_NAME]
        if not env.MULTIPLE_LOCAL_BLUEPRINTS:
            directories.append('local-storage')
        return os.path.join(*directories)


def get_storage():
    return local.FileStorage(storage_dir=storage_dir())


def load_env(blueprint_id=None):
    if not os.path.isdir(storage_dir()):
        error = exceptions.CloudifyCliError('Please initialize a blueprint')
        error.possible_solutions = ["Run `cfy init BLUEPRINT_PATH`"]
        raise error
    return local.load_env(name=blueprint_id or 'local', storage=get_storage())


def _install_plugins(blueprint_path):
    requirements = create_requirements(blueprint_path=blueprint_path)
    logger = get_logger()

    if requirements:
        # Validate we are inside a virtual env
        if not utils.is_virtual_env():
            raise exceptions.CloudifyCliError(
                'You must be running inside a '
                'virtualenv to install blueprint plugins')

        runner = LocalCommandRunner(logger)
        # Dump the requirements to a file and let pip install it.
        # This will utilize pip's mechanism of cleanup in case an installation
        # fails.
        tmp_path = tempfile.mkstemp(suffix='.txt', prefix='requirements_')[1]
        utils.dump_to_file(collection=requirements, file_path=tmp_path)
        command_parts = [sys.executable, '-m', 'pip', 'install', '-r',
                         tmp_path]
        runner.run(command=' '.join(command_parts), stdout_pipe=False)
    else:
        logger.info('There are no plugins to install')


def create_requirements(blueprint_path):
    parsed_dsl = parse_from_path(dsl_file_path=blueprint_path)

    requirements = _plugins_to_requirements(
        blueprint_path=blueprint_path,
        plugins=parsed_dsl[dsl_constants.DEPLOYMENT_PLUGINS_TO_INSTALL])

    for node in parsed_dsl['nodes']:
        requirements.update(_plugins_to_requirements(
            blueprint_path=blueprint_path,
            plugins=node['plugins']))
    return requirements


def _plugins_to_requirements(blueprint_path, plugins):

    sources = set()
    for plugin in plugins:
        if plugin[dsl_constants.PLUGIN_INSTALL_KEY]:
            source = plugin[dsl_constants.PLUGIN_SOURCE_KEY]
            if not source:
                continue
            if '://' in source:
                # URL
                sources.add(source)
            else:
                # Local plugin (should reside under the 'plugins' dir)
                plugin_path = os.path.join(
                    os.path.abspath(os.path.dirname(blueprint_path)),
                    'plugins',
                    source)
                sources.add(plugin_path)
    return sources
