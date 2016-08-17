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
import shutil

from .. import env
from .. import utils
from ..cli import cfy
from .. import blueprint
from ..config import config
from .init import init_manager_profile
from ..bootstrap import bootstrap as bs
from ..exceptions import CloudifyCliError


@cfy.command(name='bootstrap', short_help='Bootstrap a manager')
@cfy.argument('blueprint-path')
@cfy.options.blueprint_filename()
@cfy.options.inputs
@cfy.options.validate_only
@cfy.options.skip_validations
@cfy.options.skip_sanity
@cfy.options.install_plugins
@cfy.options.task_retries()
@cfy.options.task_retry_interval()
@cfy.options.task_thread_pool_size()
@cfy.options.keep_up_on_failure
@cfy.options.verbose()
@cfy.pass_logger
def bootstrap(blueprint_path,
              blueprint_filename,
              inputs,
              validate_only,
              skip_validations,
              skip_sanity,
              install_plugins,
              task_retries,
              task_retry_interval,
              task_thread_pool_size,
              keep_up_on_failure,
              logger):
    """Bootstrap a Cloudify manager

    `BLUEPRINT_PATH` is a path to the manager-blueprint used to bootstrap
    the manager.

    Note that `--validate-only` will validate resource creation without
    actually validating the host's OS type, Available Memory, etc.. as
    the host doesn't necessarily exist prior to bootstrapping.

    `--skip-validations`, on the other hand, will skip both resource
    creation validation AND any additional validations done on the host
    once it is up.
    """
    env_name = 'manager'

    temp_profile_active = False
    active_profile = env.get_active_profile()
    if not active_profile or active_profile == 'local':
        active_profile = utils.generate_random_string()
        temp_profile_active = True
        init_manager_profile(profile_name=active_profile)
        env.set_active_profile(active_profile)

    processed_blueprint_path = blueprint.get(
        blueprint_path,
        blueprint_filename
    )

    unclean_env_message = "Can't bootstrap because the environment is not " \
                          "clean. Clean the environment by calling teardown " \
                          "or reset it using the `cfy init -r` command"
    # verifying no environment exists from a previous bootstrap
    try:
        bs.load_env(env_name)
    except IOError:
        # Environment is clean
        pass
    except CloudifyCliError:
        # Will be raised if `get_profile_dir` gets called
        pass
    else:
        raise RuntimeError(unclean_env_message)

    try:
        if not skip_validations:
            logger.info('Executing bootstrap validation...')
            bs.bootstrap_validation(
                processed_blueprint_path,
                name=env_name,
                inputs=inputs,
                task_retries=task_retries,
                task_retry_interval=task_retry_interval,
                task_thread_pool_size=task_thread_pool_size,
                install_plugins=install_plugins,
                resolver=config.get_import_resolver())
            logger.info('Bootstrap validation completed successfully')
        elif inputs:
            # The user expects that `--skip-validations` will also ignore
            # bootstrap validations and not only creation_validations
            utils.add_ignore_bootstrap_validations_input(inputs)

        if not validate_only:
            try:
                logger.info('Executing manager bootstrap...')
                details = bs.bootstrap(
                    processed_blueprint_path,
                    name=env_name,
                    inputs=inputs,
                    task_retries=task_retries,
                    task_retry_interval=task_retry_interval,
                    task_thread_pool_size=task_thread_pool_size,
                    install_plugins=install_plugins,
                    skip_sanity=skip_sanity)

                # TODO: Move these two parts to a separate function?

                manager_ip = details['manager_ip']

                temp_profile = os.path.join(
                    env.PROFILES_DIR, active_profile)
                new_profile = os.path.join(
                    env.PROFILES_DIR, manager_ip)
                shutil.move(temp_profile, new_profile)
                temp_profile_active = False
                env.set_active_profile(new_profile)

                profile = env.profile
                profile.manager_ip = manager_ip
                profile.rest_port = details['rest_port']
                profile.rest_protocol = details['rest_protocol']
                profile.provider_context = details['provider_context']
                profile.manager_key = details['manager_key_path']
                profile.manager_user = details['manager_user']
                profile.manager_port = details['manager_port']
                profile.bootstrap_state = True

                # Save creates a profile folder, if it doesn't exist, so it's
                # important to do that *after* the temp profile folder was
                # moved to the real one
                profile.save()

                logger.info('Bootstrap complete')
                logger.info('Manager is up at {0}'.format(manager_ip))
            except Exception as ex:
                tpe, value, traceback = sys.exc_info()
                logger.error('Bootstrap failed! ({0})'.format(str(ex)))
                if not keep_up_on_failure:
                    try:
                        bs.load_env(env_name)
                    except (IOError, CloudifyCliError):
                        # the bootstrap exception occurred before environment
                        # was even initialized - nothing to teardown.
                        pass
                    else:
                        logger.info(
                            'Executing teardown due to failed bootstrap...')
                        bs.teardown(name=env_name,
                                    task_retries=5,
                                    task_retry_interval=30,
                                    task_thread_pool_size=1)
                raise tpe, value, traceback
    finally:
        if temp_profile_active:
            env.set_active_profile('local')
            env.delete_profile(active_profile)
