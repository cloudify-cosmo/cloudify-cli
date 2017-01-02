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
from ..constants import DEFAULT_TENANT_NAME


@cfy.command(name='bootstrap', short_help='Bootstrap a manager')
@cfy.argument('blueprint-path')
@cfy.options.blueprint_filename()
@cfy.options.inputs
@cfy.options.validate_only
@cfy.options.skip_validations
@cfy.options.skip_sanity
@cfy.options.install_plugins
@cfy.options.task_retries(5)
@cfy.options.task_retry_interval(30)
@cfy.options.task_thread_pool_size()
@cfy.options.keep_up_on_failure
@cfy.options.dont_save_password_in_profile
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
              dont_save_password_in_profile,
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

    temp_profile_active = True
    active_profile = _create_temp_profile()

    processed_blueprint_path = blueprint.get(
        blueprint_path, blueprint_filename)

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
            if not inputs.get('admin_password'):
                inputs['admin_password'] = bs.generate_password()
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
                manager_ip = details['manager_ip']

                _set_new_profile(active_profile, manager_ip)
                temp_profile_active = False
                env.set_active_profile(manager_ip)
                _set_profile_details(
                    details,
                    inputs,
                    dont_save_password_in_profile
                )
                logger.info('Bootstrap complete')
                _print_finish_message(logger, manager_ip, inputs)
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


def _print_finish_message(logger, manager_ip, inputs):
    logger.info('Manager is up at {0}'.format(manager_ip))
    logger.info('#' * 50)
    logger.info('Manager password is {0}'.format(inputs['admin_password']))
    logger.info('#' * 50)


def _create_temp_profile():
    active_profile = 'temp-' + utils.generate_random_string()
    init_manager_profile(profile_name=active_profile)
    env.set_active_profile(active_profile)
    return active_profile


def _set_new_profile(active_profile, manager_ip):
    temp_profile = os.path.join(env.PROFILES_DIR, active_profile)
    new_profile = os.path.join(env.PROFILES_DIR, manager_ip)
    if env.is_profile_exists(manager_ip):
        env.delete_profile(manager_ip)
    shutil.move(temp_profile, new_profile)


def _set_profile_details(details, inputs, dont_save_password):
    profile = env.profile
    profile.manager_ip = details['manager_ip']
    profile.rest_port = details['rest_port']
    profile.rest_protocol = details['rest_protocol']
    profile.provider_context = details['provider_context']
    profile.ssh_key = details['ssh_key_path']
    profile.ssh_user = details['ssh_user']
    profile.ssh_port = details['ssh_port']
    profile.manager_username = inputs['admin_username']
    if not dont_save_password:
        profile.manager_password = inputs['admin_password']
    profile.manager_tenant = DEFAULT_TENANT_NAME

    profile.bootstrap_state = 'Complete'
    profile.save()
