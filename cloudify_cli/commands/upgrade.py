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

"""
Handles 'cfy upgrade command'
"""
import time
import json
import tempfile

from cloudify_cli import ssh
from cloudify_cli import utils
from cloudify_cli import common
from cloudify_cli import exceptions
from cloudify_cli.logger import get_logger
from cloudify_cli.commands import maintenance


MAINTENANCE_MODE_DEACTIVATED = 'deactivated'
MAINTENANCE_MODE_ACTIVATING = 'activating'

REMOTE_WORKFLOW_STATE_PATH = '/opt/manager/_workflow_state.json'


def upgrade(validate_only,
            skip_validations,
            blueprint_path,
            inputs,
            install_plugins,
            task_retries,
            task_retry_interval,
            task_thread_pool_size):

    logger = get_logger()
    management_ip = utils.get_management_server_ip()

    client = utils.get_rest_client(management_ip)
    curr_status = client.maintenance_mode.status().status
    if curr_status == MAINTENANCE_MODE_DEACTIVATED:
        msg = "'Manager must be in maintenance mode for upgrade to run."
        error = exceptions.CloudifyCliError(msg)
        error.possible_solutions = [
            "Activate maintenance mode by running "
            "'cfy maintenance-mode activate'"
        ]
        raise error
    elif curr_status == MAINTENANCE_MODE_ACTIVATING:
        _wait_for_maintenance(client, logger)

    if not inputs:
        inputs = {}
    inputs_data = utils.inputs_to_dict(inputs, 'inputs') or {}
    if not inputs_data.get('private_ip'):
        raise exceptions.CloudifyCliError('Private IP must be provided for '
                                          'the upgrade process')
    if 'ssh_key_filename' not in inputs_data.keys():
        inputs_data.update({'ssh_key_filename': utils.get_management_key()})
    if 'public_ip' not in inputs_data.keys():
        inputs_data.update({'public_ip': management_ip})
    if 'ssh_user' not in inputs_data.keys():
        inputs_data.update({'ssh_user': utils.get_management_user()})

    env_name = 'manager-upgrade'
    # init local workflow execution environment
    env = common.initialize_blueprint(blueprint_path,
                                      storage=None,
                                      install_plugins=install_plugins,
                                      name=env_name,
                                      inputs=str(inputs_data))

    if not skip_validations:
        logger.info('Executing upgrade validations...')
        env.execute(workflow='execute_operation',
                    parameters={'operation':
                                'cloudify.interfaces.validation.creation'},
                    task_retries=task_retries,
                    task_retry_interval=task_retry_interval,
                    task_thread_pool_size=task_thread_pool_size)

    if not validate_only:
        logger.info('Starting manager upgrade process...')
        _put_workflow_state_file(is_upgrade=True)

        logger.info('Executing manager upgrade...')
        env.execute('install',
                    task_retries=task_retries,
                    task_retry_interval=task_retry_interval)

    logger.info('Deactivating manager maintenance-mode...')
    client.maintenance_mode.deactivate()


def _put_workflow_state_file(is_upgrade):
    manager_state_file = tempfile.NamedTemporaryFile(delete=True)
    content = {'is_upgrade': is_upgrade}
    with open(manager_state_file.name, 'w') as f:
        f.write(json.dumps(content))
    ssh.put_file_in_manager(manager_state_file, REMOTE_WORKFLOW_STATE_PATH)


def _wait_for_maintenance(client, logger):
    curr_status = client.maintenance_mode.status().status
    while curr_status != maintenance.MAINTENANCE_MODE_ACTIVE:
        logger.info('Waiting for maintenance mode activation...')
        time.sleep(maintenance.DEFAULT_TIMEOUT_INTERVAL)
        curr_status = client.maintenance_mode.status().status
