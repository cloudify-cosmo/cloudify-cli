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

from . import local
from .. import utils
from .. import common
from .. import constants
from .. import exceptions
from ..config import helptexts
from ..logger import get_logger
from ..logger import configure_loggers


_NAME = 'local'
_STORAGE_DIR_NAME = 'local-storage'


@click.command(name='init', context_settings=utils.CLICK_CONTEXT_SETTINGS)
@click.argument('blueprint-path',
                required=False)
@click.option('-r',
              '--reset-config',
              cls=utils.MutuallyExclusiveOption,
              mutually_exclusive=['inputs',
                                  'install_plugins'],
              mutuality_error_message='MUasdasdads',
              is_flag=True,
              help=helptexts.RESET_CONFIG)
@click.option('--skip-logging',
              cls=utils.MutuallyExclusiveOption,
              mutually_exclusive=['blueprint_path',
                                  'inputs',
                                  'install_plugins'],
              is_flag=True,
              help=helptexts.SKIP_LOGGING)
@click.option('-i',
              '--inputs',
              cls=utils.MutuallyExclusiveOption,
              mutually_exclusive=['reset_config', 'skip_logging'],
              multiple=True,
              help=helptexts.INPUTS)
@click.option('--install-plugins',
              cls=utils.MutuallyExclusiveOption,
              mutually_exclusive=['reset_config', 'skip_logging'],
              is_flag=True,
              help=helptexts.INSTALL_PLUGINS)
@click.option('--hard',
              is_flag=True)
def init_env(blueprint_path,
             reset_config,
             skip_logging,
             inputs,
             install_plugins,
             hard):
    """Initialize a working environment in the current working directory
    """
    init(blueprint_path,
         reset_config,
         skip_logging,
         inputs,
         install_plugins,
         hard)


def init(blueprint_path=None,
         reset_config=False,
         skip_logging=False,
         inputs=None,
         install_plugins=False,
         hard=False):
    def _init():
        if os.path.exists(os.path.join(
                utils.get_cwd(),
                constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
                constants.CLOUDIFY_WD_SETTINGS_FILE_NAME)):
            if not reset_config:
                error = exceptions.CloudifyCliError(
                    'Current directory is already initialized')
                error.possible_solutions = [
                    "Run 'cfy init -r' to force re-initialization "
                    "(might overwrite existing "
                    "configuration files if exist) "
                ]
                raise error
            else:
                workdir = os.path.join(
                    utils.get_cwd(),
                    constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME)
                if hard:
                    shutil.rmtree(workdir)
                else:
                    to_delete = \
                        [f for f in os.listdir(workdir) if f != 'config.yaml']
                    for f in to_delete:
                        full_path = os.path.join(workdir, f)
                        if os.path.isfile(full_path):
                            os.remove(full_path)
                        else:
                            shutil.rmtree(full_path)

        settings = utils.CloudifyWorkingDirectorySettings()
        utils.dump_cloudify_working_dir_settings(settings)
        if hard:
            utils.dump_configuration_file()
        configure_loggers()
        if not skip_logging:
            get_logger().info('Initialization completed successfully')

    if blueprint_path:
        if os.path.isdir(local._storage_dir()):
            shutil.rmtree(local._storage_dir())

        if not utils.is_initialized():
            _init(reset_config=False, skip_logging=True)
        try:
            common.initialize_blueprint(
                blueprint_path=blueprint_path,
                name=_NAME,
                inputs=inputs,
                storage=local._storage(),
                install_plugins=install_plugins,
                resolver=utils.get_import_resolver()
            )
        except ImportError as e:

            # import error indicates
            # some plugin modules are missing
            # TODO - consider adding an error code to
            # TODO - all of our exceptions. so that we
            # TODO - easily identify them here
            e.possible_solutions = [
                "Run `cfy init {0} --install-plugins`".format(blueprint_path),
                "Run `cfy local install-plugins -p {0}`".format(blueprint_path)
            ]
            raise

        get_logger().info("Initiated {0}\nIf you make changes to the "
                          "blueprint, run `cfy init {0}` "
                          "again to apply them".format(blueprint_path))
    else:
        _init()
