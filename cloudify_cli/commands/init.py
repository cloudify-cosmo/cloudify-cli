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
import shutil
import pkg_resources

from jinja2.environment import Template

import cloudify_cli
from .. import env
from .. import local
from ..cli import cfy
from .. import blueprint
from .. import exceptions
from ..config import config
from ..logger import DEFAULT_LOG_FILE
from ..logger import configure_loggers
from ..exceptions import CloudifyCliError


@cfy.command(name='init', short_help='Initialize a working env')
@cfy.argument('blueprint-path', required=False)
@cfy.options.blueprint_filename()
@cfy.options.blueprint_id(required=False, multiple_blueprints=True)
@cfy.options.reset_context
@cfy.options.inputs
@cfy.options.install_plugins
@cfy.options.init_hard_reset
@cfy.options.enable_colors
@cfy.options.verbose()
@cfy.pass_logger
def init(blueprint_path,
         blueprint_filename,
         blueprint_id,
         reset_context,
         inputs,
         install_plugins,
         hard,
         enable_colors,
         logger):
    """Initialize a Cloudify environment.

    This is required to perform many actions and should be the first
    action performed after installing Cloudify.

    Note: Running `cfy install` or `cfy profiles use` will
    initialize an environment automatically.

    Providing a `BLUEPRINT_PATH` will also initialize a blueprint to
    work on.

    After initialization, the CLI's configuration can be found under
    ~/.cloudify/config.yaml. For more information refer to the docs
    at http://docs.getcloudify.org
    """
    profile_name = 'local'

    if blueprint_path:
        if reset_context or hard:
            logger.warning(
                'The `--reset-context` and `--hard` flags are ignored '
                'when initializing a blueprint')

        init_local_profile(
            reset_context=True,
            hard=False,
            enable_colors=enable_colors
        )
        env.set_active_profile(profile_name)

        processed_blueprint_path = blueprint.get(
            blueprint_path,
            blueprint_filename
        )

        if env.MULTIPLE_LOCAL_BLUEPRINTS:
            blueprint_id = blueprint_id or blueprint.generate_id(
                processed_blueprint_path,
                blueprint_filename
            )

        if os.path.isdir(local.storage_dir(blueprint_id)):
            shutil.rmtree(local.storage_dir(blueprint_id))

        try:
            storage = local.get_storage()
            local.initialize_blueprint(
                blueprint_path=processed_blueprint_path,
                name=blueprint_id or 'local',
                inputs=inputs,
                storage=storage,
                install_plugins=install_plugins,
                resolver=config.get_import_resolver()
            )
        except ImportError as e:
            e.possible_solutions = [
                "Run `cfy init {0} --install-plugins`".format(blueprint_path),
                "Run `cfy install-plugins {0}`".format(blueprint_path)
            ]
            raise

        logger.info("Initialized {0}\nIf you make changes to the "
                    "blueprint, run `cfy init {0}` "
                    "again to apply them".format(blueprint_path))
    else:
        if env.is_initialized() and not (reset_context or hard):
            raise CloudifyCliError(
                'Environment is already initialized. '
                'You can reset the environment by running `cfy init -r`')
        init_local_profile(reset_context, hard, enable_colors)
        env.set_active_profile(profile_name)


@cfy.pass_logger
def init_local_profile(reset_context=False,
                       hard=False,
                       enable_colors=False,
                       logger=None):
    logger.info('Initializing local profile ...')

    if reset_context:
        if hard:
            os.remove(config.CLOUDIFY_CONFIG_PATH)
    # else:
    #     TODO: Is this check necessary?
        # _raise_initialized_error('local')

    _create_profiles_dir_and_config(hard, enable_colors)
    logger.info('Initialization completed successfully')


@cfy.pass_logger
def init_manager_profile(profile_name,
                         reset_context=False,
                         hard=False,
                         enable_colors=False,
                         logger=None):
    logger.info('Initializing profile {0}...'.format(profile_name))

    context_file_path = env.get_context_path(profile_name, suppress_error=True)

    if context_file_path and os.path.isfile(context_file_path):
        if reset_context:
            if hard:
                os.remove(config.CLOUDIFY_CONFIG_PATH)
            else:
                os.remove(context_file_path)
        else:
            _raise_initialized_error(profile_name)

    _create_profiles_dir_and_config(hard, enable_colors)

    profile = env.ProfileContext()
    profile.manager_ip = profile_name
    profile.save()

    logger.info('Initialization completed successfully')


def _create_profiles_dir_and_config(hard, enable_colors):
    if not os.path.isdir(env.PROFILES_DIR):
        os.makedirs(env.PROFILES_DIR)
    if not os.path.isfile(config.CLOUDIFY_CONFIG_PATH) or hard:
        set_config(enable_colors=enable_colors)

    configure_loggers()


def _raise_initialized_error(profile_name):
    error = exceptions.CloudifyCliError(
        '{0} profile already initialized'.format(profile_name))
    error.possible_solutions = [
        "Run 'cfy init -r' to force re-initialization "
    ]
    raise error


def set_config(enable_colors=False):
    cli_config = pkg_resources.resource_string(
        cloudify_cli.__name__,
        'config/config_template.yaml')

    enable_colors = str(enable_colors).lower()
    template = Template(cli_config)
    rendered = template.render(
        log_path=DEFAULT_LOG_FILE,
        enable_colors=enable_colors
    )
    with open(config.CLOUDIFY_CONFIG_PATH, 'w') as f:
        f.write(rendered)
        f.write(os.linesep)
