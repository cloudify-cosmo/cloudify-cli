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
import sys
import shutil

import click

from .. import utils
from .. import common
from ..config import cfy
from .init import init_profile
from ..config import helptexts
from ..logger import get_logger
from ..bootstrap import bootstrap as bs


@cfy.command(name='bootstrap')
@cfy.options.inputs
@cfy.options.validate_only
@cfy.options.skip_validations
@cfy.options.install_plugins
@cfy.options.task_retries()
@cfy.options.task_retry_interval()
@cfy.options.task_thread_pool_size()
@click.argument('blueprint-path', required=True)
@click.option('--keep-up-on-failure',
              help=helptexts.KEEP_UP_ON_FAILURE)
def bootstrap(blueprint_path,
              inputs,
              validate_only,
              skip_validations,
              install_plugins,
              task_retries,
              task_retry_interval,
              task_thread_pool_size,
              keep_up_on_failure):
    """Bootstrap a manager

    Note that `--validate-only` will validate resource creation without
    actually validating the host's OS type, Available Memory, etc.. as
    the host doesn't necessarily exist prior to bootstrapping.

    `--skip-validations`, on the other hand, will skip both resource
    creation validation AND any additional validations done on the host
    once it is up.
    """
    # This must be a list so that we can append to it if necessary.
    inputs = list(inputs)

    logger = get_logger()
    env_name = 'manager'

    # TODO: propagate key, user, etc.. to inputs
    # TODO: delete temporary profile if bootstrap failed
    # TODO: allow to skip sanity
    temp_profile_active = False
    active_profile = utils.get_active_profile()
    if not active_profile or active_profile == 'local':
        active_profile = utils.generate_random_string()
        temp_profile_active = True
        init_profile(profile_name=active_profile)

    # verifying no environment exists from a previous bootstrap
    try:
        bs.load_env(env_name)
    except IOError:
        # Environment is clean
        pass
    else:
        raise RuntimeError(
            "Can't bootstrap because the environment is not clean. Clean the "
            'environment by calling teardown or reset it using the "cfy init '
            '-r" command')

    try:
        if not skip_validations:
            logger.info('Executing bootstrap validation...')
            bs.bootstrap_validation(
                blueprint_path,
                name=env_name,
                inputs=inputs,
                task_retries=task_retries,
                task_retry_interval=task_retry_interval,
                task_thread_pool_size=task_thread_pool_size,
                install_plugins=install_plugins,
                resolver=utils.get_import_resolver())
            logger.info('Bootstrap validation completed successfully')
        elif inputs:
            # The user expects that `--skip-validations` will also ignore
            # bootstrap validations and not only creation_validations
            inputs = common.add_ignore_bootstrap_validations_input(inputs)

        if not validate_only:
            try:
                logger.info('Executing manager bootstrap...')
                details = bs.bootstrap(
                    blueprint_path,
                    name=env_name,
                    inputs=inputs,
                    task_retries=task_retries,
                    task_retry_interval=task_retry_interval,
                    task_thread_pool_size=task_thread_pool_size,
                    install_plugins=install_plugins)

                manager_ip = details['manager_ip']
                with utils.update_wd_settings(active_profile) as profile:
                    profile.set_management_server(manager_ip)
                    profile.set_management_key(details['manager_key_path'])
                    profile.set_management_user(details['manager_user'])
                    profile.set_provider_context(details['provider_context'])
                    profile.set_rest_port(details['rest_port'])
                    profile.set_protocol(details['protocol'])
                    profile.set_bootstrap_state(True)

                temp_profile = os.path.join(
                    utils.PROFILES_DIR, active_profile)
                new_profile = os.path.join(
                    utils.PROFILES_DIR, manager_ip)
                shutil.move(temp_profile, new_profile)
                utils.set_active_profile(new_profile)

                logger.info('Bootstrap complete')
                logger.info('Manager is up at {0}'.format(manager_ip))
            except Exception as ex:
                tpe, value, traceback = sys.exc_info()
                logger.error('Bootstrap failed! ({0})'.format(str(ex)))
                if not keep_up_on_failure:
                    try:
                        bs.load_env(env_name)
                    except IOError:
                        # the bootstrap exception occurred before environment
                        # was even initialized - nothing to teardown.
                        pass
                    else:
                        logger.info(
                            'Executing teardown due to failed bootstrap...')
                        # TODO: why are we not propagating to this one?
                        bs.teardown(name=env_name,
                                    task_retries=5,
                                    task_retry_interval=30,
                                    task_thread_pool_size=1)
                raise tpe, value, traceback
    finally:
        if temp_profile_active:
            utils.delete_profile(active_profile)
