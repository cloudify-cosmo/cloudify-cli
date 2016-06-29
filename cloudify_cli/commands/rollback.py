########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

import json

import click

from .. import utils
from .. import common
from ..config import cfy
from .. import exceptions
from ..logger import get_logger
from .upgrade import update_inputs
from .upgrade import put_workflow_state_file
from .upgrade import verify_and_wait_for_maintenance_mode_activation


@cfy.command(name='rollback')
@click.argument('blueprint-path', required=True)
@cfy.options.inputs
@cfy.options.install_plugins
@cfy.options.task_retries()
@cfy.options.task_retry_interval()
@cfy.options.task_thread_pool_size()
def rollback(blueprint_path,
             inputs,
             install_plugins,
             task_retries,
             task_retry_interval,
             task_thread_pool_size):
    """Rollback a manager to its previous version

    Note that you can only rollback to the last version you upgraded from.
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()

    client = utils.get_rest_client(management_ip, skip_version_check=True)

    verify_and_wait_for_maintenance_mode_activation(client)

    inputs = update_inputs(inputs)

    env_name = 'manager-rollback'
    # init local workflow execution environment
    env = common.initialize_blueprint(blueprint_path,
                                      storage=None,
                                      install_plugins=install_plugins,
                                      name=env_name,
                                      inputs=json.dumps(inputs))

    logger.info('Starting Manager rollback process...')
    put_workflow_state_file(is_upgrade=False,
                            key_filename=inputs['ssh_key_filename'],
                            user=inputs['ssh_user'])

    logger.info('Executing Manager rollback...')
    try:
        env.execute('install',
                    task_retries=task_retries,
                    task_retry_interval=task_retry_interval,
                    task_thread_pool_size=task_thread_pool_size)
    except Exception as e:
        msg = 'Failed to rollback Manager upgrade. Error: {0}'.format(e)
        raise exceptions.CloudifyCliError(msg)

    logger.info('Rollback complete. Management server is up at {0}'
                .format(inputs['public_ip']))
