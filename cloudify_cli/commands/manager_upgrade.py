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
import yaml
import time
import json
import tempfile
from contextlib import contextmanager

from cloudify_cli import utils
from cloudify_cli import common
from cloudify_cli.logger import get_logger
from cloudify_cli.commands import maintenance

import fabric.api
import fabric.context_managers

MAINTENANCE_MODE_DEACTIVATED = 'deactivated'

REMOTE_WORKFLOW_STATE_PATH = '/opt/manager/_workflow_state.json'

logger = get_logger()


def upgrade(validate_only,
            skip_validations,
            blueprint_path,
            inputs,
            install_plugins,
            task_retries,
            task_retry_interval,
            task_thread_pool_size):

    env_name = 'manager-upgrade'

    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    curr_status = client.maintenance_mode.status().status
    if curr_status == MAINTENANCE_MODE_DEACTIVATED:
        logger.info('Activating manager maintenance mode.')
        client.maintenance_mode.activate()
    _wait_for_maintenance(client, curr_status)

    # init local workflow execution environment
    env = common.initialize_blueprint(blueprint_path,
                                      storage=None,
                                      install_plugins=install_plugins,
                                      name=env_name,
                                      inputs=inputs)

    if not skip_validations:
        logger.info('Executing upgrade validation')
        env.execute(workflow='execute_operation',
                    parameters={'operation':
                                'cloudify.interfaces.validation.creation'},
                    task_retries=task_retries,
                    task_retry_interval=task_retry_interval,
                    task_thread_pool_size=task_thread_pool_size)

    if not validate_only:
        with open(inputs) as f:
            inputs_data = yaml.load(f)
        fabric_data = {'host_string': management_ip,
                       'user': inputs_data['ssh_user'],
                       'key_filename': inputs_data['ssh_key_filename']}

        logger.info('Starting manager upgrade process.')
        _set_workflow_flag_to_update(fabric_data)
        try:
            logger.info('Executing manager upgrade.')
            env.execute('install',
                        task_retries=task_retries,
                        task_retry_interval=task_retry_interval)
        except Exception as e:
            logger.info('Upgrade process failed. Starting manager '
                        'rollback')
            _set_workflow_flag_to_rollback(fabric_data)
            # env.execute('install',
            #             task_retries=task_retries,
            #             task_retry_interval=task_retry_interval)
            # logger.info('Manager rollback process ended successfully')
            raise e
        # finally:
        #     try:
        #         _delete_workflow_flag_file(fabric_data)
        #     except:
        #         logger.info('Upgrade remote data cleanup failed.')

    logger.info('Deactivating manager maintenance-mode')
    client.maintenance_mode.deactivate()


def _set_workflow_flag_to_update(fabric_data):
    manager_state_file = tempfile.NamedTemporaryFile(delete=True)
    content = {'is_upgrade': True}
    with open(manager_state_file.name, 'w') as f:
        f.write(json.dumps(content))

    _put_workflow_state_file(fabric_data, manager_state_file.name)


def _put_workflow_state_file(fabric_data, manager_state_file):
    with _manager_fabric_env(**fabric_data) as api:
        api.put(use_sudo=True,
                local_path=manager_state_file,
                remote_path=REMOTE_WORKFLOW_STATE_PATH)


def _set_workflow_flag_to_rollback(fabric_data):
    manager_state_file = tempfile.NamedTemporaryFile(delete=True)
    with _manager_fabric_env(**fabric_data) as api:
        with open(manager_state_file.name, 'r+') as f:
            api.get(REMOTE_WORKFLOW_STATE_PATH, f.name)
            content = json.load(f)
            content.update({'is_upgrade': False})
            json.dump(json.dumps(content), f)
    _put_workflow_state_file(fabric_data, manager_state_file.name)


def _delete_workflow_flag_file(fabric_data):
    with _manager_fabric_env(**fabric_data) as api:
        api.run('rm {0}'.format(REMOTE_WORKFLOW_STATE_PATH))


def _wait_for_maintenance(client, curr_status):
    while curr_status != maintenance.MAINTENANCE_MODE_ACTIVE:
        logger.info('Waiting for maintenance mode activation.')
        time.sleep(maintenance.DEFAULT_TIMEOUT_INTERVAL)
        curr_status = client.maintenance_mode.status().status


@contextmanager
def _manager_fabric_env(**kwargs):
    with fabric.context_managers.settings(**kwargs):
        yield fabric.api
