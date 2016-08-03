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

from cloudify.workflows import local

from . import env
from . import constants
from . import exceptions
from .logger import get_logger


_ENV_NAME = 'local'
_STORAGE_DIR_NAME = 'local-storage'


# TODO: Consolidate utils/common


def initialize_blueprint(blueprint_path,
                         name,
                         storage,
                         install_plugins=False,
                         inputs=None,
                         resolver=None):
    logger = get_logger()

    logger.info('Initializing blueprint...')
    if install_plugins:
        install_blueprint_plugins(blueprint_path=blueprint_path)

    config = env.CloudifyConfig()
    return local.init_env(
        blueprint_path=blueprint_path,
        name=name,
        inputs=inputs,
        storage=storage,
        ignored_modules=constants.IGNORED_LOCAL_WORKFLOW_MODULES,
        provider_context=config.local_provider_context,
        resolver=resolver,
        validate_version=config.validate_definitions_version)


def add_ignore_bootstrap_validations_input(inputs):
    """This is used when passing the `--skip-validations` flag as we
    also want to skip bootstrap validations, not just `creation_validation`
    operations.
    """
    assert isinstance(inputs, dict)
    inputs.update({'ignore_bootstrap_validations': True})


def storage_dir():
    return os.path.join(env.PROFILES_DIR, _ENV_NAME, _STORAGE_DIR_NAME)


def storage():
    return local.FileStorage(storage_dir=storage_dir())


def load_env():
    if not os.path.isdir(storage_dir()):
        error = exceptions.CloudifyCliError('Please initialize a blueprint')
        error.possible_solutions = ["Run `cfy init BLUEPRINT_PATH`"]
        raise error
    return local.load_env(name=_ENV_NAME, storage=storage())
