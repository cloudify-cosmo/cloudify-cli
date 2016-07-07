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

import os
import shutil

import click

from .. import utils
from .. import common
from .. import constants
from .. import exceptions
from ..config import cfy
from ..logger import get_logger
from ..logger import configure_loggers


_NAME = 'local'


# cfy init my_profile
# cfy use my_profile -t ...
# cfy init my_profile -r

@cfy.command(name='init')
@click.argument('profile-name', required=False)
@cfy.options.blueprint_path()
@cfy.options.reset_config
@cfy.options.skip_logging
@cfy.options.inputs
@cfy.options.install_plugins
@cfy.options.init_hard_reset
def init(profile_name,
         blueprint_path,
         reset_config,
         skip_logging,
         inputs,
         install_plugins,
         hard):
    """Initialize a working environment in the current working directory
    """
    logger = get_logger()

    def _init(profile_name=None):
        logger.info('Initializing profile {0}'.format(profile_name))
        profile_name = profile_name or 'default'

        context_file_path = os.path.join(
            utils.CLOUDIFY_WORKDIR,
            profile_name,
            constants.CLOUDIFY_WD_SETTINGS_FILE_NAME)

        if os.path.isfile(context_file_path):
            if reset_config:
                if hard:
                    os.remove(utils.CLOUDIFY_CONFIG_PATH)
                else:
                    os.remove(context_file_path)
            else:
                error = exceptions.CloudifyCliError(
                    'Profile is already initialized')
                error.possible_solutions = [
                    "Run 'cfy init -r' to force re-initialization "
                ]
                raise error

        if not os.path.isdir(utils.CLOUDIFY_WORKDIR):
            os.makedirs(utils.CLOUDIFY_WORKDIR)
        utils.update_active_profile(profile_name)
        if not os.path.isdir(utils.CLOUDIFY_CONFIG_PATH) or hard:
            utils.dump_configuration_file()

        settings = utils.CloudifyWorkingDirectorySettings()
        utils.dump_cloudify_working_dir_settings(
            settings, profile_name=profile_name)

        configure_loggers()
        if not skip_logging:
            logger.info('Initialization completed successfully')

    if blueprint_path:
        if os.path.isdir(common.storage_dir()):
            shutil.rmtree(common.storage_dir())

        if not utils.is_initialized():
            _init(reset_config=False, skip_logging=True)
        try:
            common.initialize_blueprint(
                blueprint_path=blueprint_path,
                name=_NAME,
                inputs=inputs,
                storage=common.storage(),
                install_plugins=install_plugins,
                resolver=utils.get_import_resolver()
            )
        except ImportError as e:

            # import error indicates
            # some plugin modules are missing
            # TODO: consider adding an error code to
            # all of our exceptions. so that we
            # easily identify them here
            e.possible_solutions = [
                "Run `cfy init {0} --install-plugins`".format(blueprint_path),
                "Run `cfy install-plugins {0}`".format(blueprint_path)
            ]
            raise

        logger.info("Initialized {0}\nIf you make changes to the "
                    "blueprint, run `cfy init {0}` "
                    "again to apply them".format(blueprint_path))
    else:
        _init(profile_name)
