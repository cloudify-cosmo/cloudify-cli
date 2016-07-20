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

from .. import utils
from .. import common
from .. import constants
from .. import exceptions
from ..config import cfy
from ..logger import get_logger
from ..logger import configure_loggers
from ..bootstrap import bootstrap as bs
from ..exceptions import CloudifyCliError


@cfy.command(name='init')
@cfy.argument('blueprint-path', required=False)
@cfy.options.reset_context
@cfy.options.inputs
@cfy.options.install_plugins
@cfy.options.init_hard_reset
@cfy.options.verbose
def init(blueprint_path,
         reset_context,
         inputs,
         install_plugins,
         hard):
    """Initialize a Cloudify environment.

    This is required to perform many actions and should be the first
    action performed after installing Cloudify.

    Note: Running `cfy bootstrap`, `cfy intall` or `cfy use` will
    initialize a environment automatically.

    Providing a `BLUEPRINT_PATH` will also initialize a blueprint to
    work on.

    After initialization, the CLI's configuration can be found under
    ~/.cloudify/config.yaml. For more information refer to the docs
    at http://docs.getcloudify.org
    """

    logger = get_logger()
    profile_name = 'local'

    # TODO: Consider replacing `cfy init BLUEPRINT_PATH` with
    # `cfy blueprints init BLUEPRINT_PATH` for local.

    if blueprint_path:
        if reset_context or hard:
            logger.warning(
                'The `--reset-context` and `--hard` flags are ignored '
                'when initalizing a blueprint')
        init_profile(profile_name, reset_context=True, hard=False)
        utils.set_active_profile(profile_name)

        if os.path.isdir(common.storage_dir()):
            shutil.rmtree(common.storage_dir())

        try:
            common.initialize_blueprint(
                blueprint_path=blueprint_path,
                name='local',
                inputs=inputs,
                storage=common.storage(),
                install_plugins=install_plugins,
                resolver=utils.get_import_resolver()
            )
        except ImportError as e:

            # ImportError indicates
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
        if utils.is_initialized() and not (reset_context or hard):
            raise CloudifyCliError(
                'Environment is already initialized. '
                'You can reset the environment by running `cfy init -r`')
        init_profile(profile_name, reset_context, hard)
        utils.set_active_profile(profile_name)


def init_profile(profile_name, reset_context=False, hard=False):
    # TODO: support profile aliases
    logger = get_logger()
    logger.info('Initializing profile {0}...'.format(profile_name))

    context_file_path = os.path.join(
        utils.PROFILES_DIR,
        profile_name,
        constants.CLOUDIFY_WD_SETTINGS_FILE_NAME)

    if os.path.isfile(context_file_path):
        if reset_context:
            if hard:
                os.remove(utils.CLOUDIFY_CONFIG_PATH)
            else:
                os.remove(context_file_path)
            bs.delete_workdir()
        else:
            error = exceptions.CloudifyCliError(
                '{0} profile already initialized'.format(profile_name))
            error.possible_solutions = [
                "Run 'cfy init -r' to force re-initialization "
            ]
            raise error

    if not os.path.isdir(utils.PROFILES_DIR):
        os.makedirs(utils.PROFILES_DIR)
    utils.set_active_profile(profile_name)
    if not os.path.isfile(utils.CLOUDIFY_CONFIG_PATH) or hard:
        utils.dump_configuration_file()

    # TODO: Verify that we don't break anything!
    if not profile_name == 'local':
        settings = utils.CloudifyWorkingDirectorySettings()
        utils.dump_cloudify_working_dir_settings(
            settings, profile_name=profile_name)

    configure_loggers()
    logger.info('Initialization completed successfully')
