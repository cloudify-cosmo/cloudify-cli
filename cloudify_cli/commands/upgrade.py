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

import os
import time
import json
import shutil
import tempfile

from .. import ssh
from .. import env
from .. import common
from ..config import cfy
from .. import exceptions
from ..bootstrap import bootstrap as bs
from ..bootstrap.bootstrap import load_env

from . import maintenance_mode


MAINTENANCE_MODE_DEACTIVATED = 'deactivated'
MAINTENANCE_MODE_ACTIVATING = 'activating'

REMOTE_WORKFLOW_STATE_PATH = '/opt/cloudify/_workflow_state.json'


@cfy.command(name='upgrade',
             short_help='Upgrade a manager to a new version [manager only]')
@cfy.argument('blueprint-path')
@cfy.options.inputs
@cfy.options.validate_only
@cfy.options.skip_validations
@cfy.options.install_plugins
@cfy.options.task_retries()
@cfy.options.task_retry_interval()
@cfy.options.task_thread_pool_size()
@cfy.options.verbose
@cfy.add_logger
@cfy.assert_manager_active
@cfy.add_client(skip_version_check=True)
def upgrade(blueprint_path,
            inputs,
            validate_only,
            skip_validations,
            install_plugins,
            task_retries,
            task_retry_interval,
            task_thread_pool_size,
            logger,
            client):
    """Upgrade a manager to a newer version

    Note that you must supply a simple-manager-blueprint to perform
    the upgrade and provide it with the relevant inputs.

    `BLUEPRINT_PATH` is the path of the manager blueprint to use for upgrade.
    """

    manager_ip = env.get_rest_host()
    verify_and_wait_for_maintenance_mode_activation(client)

    if skip_validations:
        # The user expects that `--skip-validations` will also ignore
        # bootstrap validations and not only creation_validations
        common.add_ignore_bootstrap_validations_input(inputs)

    inputs = update_inputs(inputs)

    env_name = 'manager-upgrade'
    # init local workflow execution environment
    working_env = common.initialize_blueprint(blueprint_path,
                                              storage=None,
                                              install_plugins=install_plugins,
                                              name=env_name,
                                              inputs=inputs)
    logger.info('Upgrading manager...')
    put_workflow_state_file(is_upgrade=True,
                            key_filename=inputs['ssh_key_filename'],
                            user=inputs['ssh_user'],
                            port=inputs['ssh_port'])
    if not skip_validations:
        logger.info('Executing upgrade validations...')
        working_env.execute(workflow='execute_operation',
                            parameters={
                                'operation':
                                    'cloudify.interfaces.validation.creation'},
                            task_retries=task_retries,
                            task_retry_interval=task_retry_interval,
                            task_thread_pool_size=task_thread_pool_size)
        logger.info('Upgrade validation completed successfully')

    if not validate_only:
        try:
            logger.info('Executing manager upgrade...')
            working_env.execute('install',
                                task_retries=task_retries,
                                task_retry_interval=task_retry_interval,
                                task_thread_pool_size=task_thread_pool_size)
        except Exception as e:
            msg = 'Upgrade failed! ({0})'.format(e)
            error = exceptions.CloudifyCliError(msg)
            error.possible_solutions = [
                "Rerun upgrade: `cfy upgrade`",
                "Execute rollback: `cfy rollback`"
            ]
            raise error

        manager_node = next(node for node in working_env.storage.get_nodes()
                            if node.id == 'manager_configuration')
        upload_resources = \
            manager_node.properties['cloudify'].get('upload_resources', {})
        dsl_resources = upload_resources.get('dsl_resources', ())
        if dsl_resources:
            fetch_timeout = upload_resources.get('parameters', {}) \
                .get('fetch_timeout', 30)
            fabric_env = bs.build_fabric_env(manager_ip,
                                             inputs['ssh_user'],
                                             inputs['ssh_key_filename'],
                                             inputs['ssh_port'])
            temp_dir = tempfile.mkdtemp()
            try:
                logger.info('Uploading dsl resources...')
                bs.upload_dsl_resources(dsl_resources,
                                        temp_dir=temp_dir,
                                        fabric_env=fabric_env,
                                        retries=task_retries,
                                        wait_interval=task_retry_interval,
                                        timeout=fetch_timeout)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        plugin_resources = upload_resources.get('plugin_resources', ())
        if plugin_resources:
            logger.warn('Plugins upload is not supported for upgrade. Plugins '
                        '{0} will not be uploaded'
                        .format(plugin_resources))

    logger.info('Upgrade complete')
    logger.info('Manager is up at {0}'.format(
        env.get_rest_host()))


def update_inputs(inputs=None):
    inputs = inputs or dict()
    inputs.update({'private_ip': _load_private_ip(inputs)})
    inputs.update({'ssh_key_filename': _load_manager_key(inputs)})
    inputs.update({'ssh_user': _load_manager_user(inputs)})
    inputs.update({'ssh_port': _load_manager_port(inputs)})
    inputs.update({'public_ip': env.get_rest_host()})
    return inputs


def _load_private_ip(inputs):
    try:
        return inputs['private_ip'] or load_env().outputs()['private_ip']
    except Exception:
        raise exceptions.CloudifyCliError('Private IP must be provided for '
                                          'the upgrade/rollback process')


def _load_manager_key(inputs):
    try:
        key_path = inputs.get('ssh_key_filename') or env.get_manager_key()
        return os.path.expanduser(key_path)
    except Exception:
        raise exceptions.CloudifyCliError('Manager key must be provided for '
                                          'the upgrade/rollback process')


def _load_manager_user(inputs):
    try:
        return inputs.get('ssh_user') or env.get_manager_user()
    except Exception:
        raise exceptions.CloudifyCliError('Manager user must be provided for '
                                          'the upgrade/rollback process')


def _load_manager_port(inputs):
    try:
        return inputs.get('ssh_port') or env.get_manager_port()
    except Exception:
        raise exceptions.CloudifyCliError('Manager port must be provided for '
                                          'the upgrade/rollback process')


@cfy.add_logger
def verify_and_wait_for_maintenance_mode_activation(client, logger):
    curr_status = client.maintenance_mode.status().status
    if curr_status == MAINTENANCE_MODE_DEACTIVATED:
        error = exceptions.CloudifyCliError(
            'To perform an upgrade of a manager to a newer version, '
            'the manager must be in maintenance mode')
        error.possible_solutions = [
            "Activate maintenance mode by running "
            "`cfy maintenance-mode activate`"
        ]
        raise error
    elif curr_status == MAINTENANCE_MODE_ACTIVATING:
        _wait_for_maintenance(client, logger)


def put_workflow_state_file(is_upgrade, key_filename, user, port):
    manager_state_file = tempfile.NamedTemporaryFile(delete=True)
    content = {'is_upgrade': is_upgrade}
    with open(manager_state_file.name, 'w') as f:
        f.write(json.dumps(content))
    ssh.put_file_in_manager(manager_state_file,
                            REMOTE_WORKFLOW_STATE_PATH,
                            key_filename=key_filename,
                            user=user,
                            port=port)


def _wait_for_maintenance(client, logger):
    curr_status = client.maintenance_mode.status().status
    while curr_status != maintenance_mode.MAINTENANCE_MODE_ACTIVE:
        logger.info('Waiting for maintenance mode to be activated...')
        time.sleep(maintenance_mode.DEFAULT_TIMEOUT_INTERVAL)
        curr_status = client.maintenance_mode.status().status
