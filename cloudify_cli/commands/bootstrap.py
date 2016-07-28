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

from .. import env
from .. import utils
from .. import common
from ..config import cfy
from ..bootstrap import bootstrap as bs

from .init import init_profile


@cfy.command(name='bootstrap', short_help='Bootstrap a manager')
@cfy.argument('blueprint-path')
@cfy.options.inputs
@cfy.options.validate_only
@cfy.options.skip_validations
@cfy.options.skip_sanity
@cfy.options.install_plugins
@cfy.options.task_retries()
@cfy.options.task_retry_interval()
@cfy.options.task_thread_pool_size()
@cfy.options.keep_up_on_failure
@cfy.options.verbose
@cfy.add_logger
def bootstrap(blueprint_path,
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
    # TODO: use `common.get_blueprint` to allow to bootstrap from an archive,
    # github, etc..

    env_name = 'manager'

    # TODO: allow to skip sanity
    temp_profile_active = False
    active_profile = env.get_active_profile()
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
                resolver=env.get_import_resolver())
            logger.info('Bootstrap validation completed successfully')
        elif inputs:
            # The user expects that `--skip-validations` will also ignore
            # bootstrap validations and not only creation_validations
            common.add_ignore_bootstrap_validations_input(inputs)

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
                    install_plugins=install_plugins,
                    skip_sanity=skip_sanity)

                manager_ip = details['manager_ip']
                env.update_profile_context(
                    management_ip=manager_ip,
                    management_key=details['manager_key_path'],
                    management_user=details['manager_user'],
                    management_port=details['manager_port'],
                    rest_port=details['rest_port'],
                    rest_protocol=details['rest_protocol'],
                    provider_context=details['provider_context'],
                    bootstrap_state=True)

                temp_profile = os.path.join(
                    env.PROFILES_DIR, active_profile)
                new_profile = os.path.join(
                    env.PROFILES_DIR, manager_ip)
                shutil.move(temp_profile, new_profile)
                temp_profile_active = False
                env.set_active_profile(new_profile)

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
            env.delete_profile(active_profile)
