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

import sys

import click

from cloudify_cli import utils
from cloudify_cli import common
from cloudify_cli.config import helptexts
from cloudify_cli.logger import get_logger
from cloudify_cli.bootstrap import bootstrap as bs


@click.command(name='bootstrap')
@click.argument('blueprint-path', required=True)
@click.option('-i',
              '--inputs',
              multiple=True,
              help=helptexts.INPUTS)
@click.option('--keep-up-on-failure',
              required=False,
              help=helptexts.KEEP_UP_ON_FAILURE)
@click.option('--validate_only',
              is_flag=True,
              help=helptexts.VALIDATE_ONLY)
@click.option('--skip-validations',
              is_flag=True,
              help=helptexts.SKIP_BOOTSTRAP_VALIDATIONS)
@click.option('--install-plugins',
              is_flag=True,
              help=helptexts.INSTALL_PLUGINS)
@click.option('--task-retries',
              type=int,
              default=0,
              help=helptexts.TASK_RETRIES)
@click.option('--task-retry-interval',
              type=int,
              default=1,
              help=helptexts.TASK_RETRIES)
@click.option('--task-thread-pool-size',
              type=int,
              default=1,
              help=helptexts.TASK_THREAD_POOL_SIZE)
def bootstrap(blueprint_path,
              inputs,
              keep_up_on_failure,
              validate_only,
              skip_validations,
              install_plugins,
              task_retries,
              task_retry_interval,
              task_thread_pool_size):
    """Bootstrap a manager

    Note that `--validate-only` will validate resource creation without
    actually validating the host's OS type, Available Memory, etc.. as
    the host doesn't necessarily exist prior to bootstrapping.

    `--skip-validations`, on the other hand, will skip both resource
    creation validation AND any additional validations done on the host
    once it is up.
    """
    logger = get_logger()
    env_name = 'manager'

    # Verify directory is initialized
    utils.get_context_path()

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
            provider_context = details['provider_context']
            with utils.update_wd_settings() as ws_settings:
                ws_settings.set_management_server(manager_ip)
                ws_settings.set_management_key(details['manager_key_path'])
                ws_settings.set_management_user(details['manager_user'])
                ws_settings.set_provider_context(provider_context)
                ws_settings.set_rest_port(details['rest_port'])
                ws_settings.set_protocol(details['protocol'])

            logger.info('Bootstrap complete')
            logger.info('Manager is up at {0}'.format(manager_ip))
        except Exception as ex:
            tpe, value, traceback = sys.exc_info()
            logger.error('Bootstrap failed! ({0})'.format(str(ex)))
            if not keep_up_on_failure:
                try:
                    bs.load_env(env_name)
                except IOError:
                    # the bootstrap exception occurred before environment was
                    # even initialized - nothing to teardown.
                    pass
                else:
                    logger.info(
                        'Executing teardown due to failed bootstrap...')
                    bs.teardown(name=env_name,
                                task_retries=5,
                                task_retry_interval=30,
                                task_thread_pool_size=1)
            raise tpe, value, traceback
