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

import time

from cloudify_cli import exceptions
from cloudify_cli.cli import cfy
from cloudify_cli.logger import NO_VERBOSE, get_global_verbosity
from cloudify_cli.table import print_data


DEFAULT_TIMEOUT_INTERVAL = 5
MAINTENANCE_MODE_ACTIVE = 'activated'
EXECUTION_COLUMNS = ['id', 'deployment_id', 'workflow_id', 'status']


@cfy.group(name='maintenance-mode')
@cfy.options.common_options
@cfy.assert_manager_active()
def maintenance_mode():
    """Handle the manager's maintenance-mode
    """
    pass


@maintenance_mode.command(name='status',
                          short_help='Show maintenance-mode status '
                          '[manager only]')
@cfy.options.common_options
@cfy.pass_client()
@cfy.options.extended_view
def status(client):
    """Retrieve the current maintenance-mode status.
    """
    _print_maintenance_mode_status(client)


@cfy.pass_logger
def _print_maintenance_mode_status(client, logger):
    status_response = client.maintenance_mode.status()

    logger.info('\nMaintenance Mode Status:')
    for param_name, param_value in status_response.items():
        if param_value and param_name != 'remaining_executions':
            logger.info('\t{0}:\t{1}'.format(
                param_name.title().replace("_", " "),
                param_value))
    logger.info('')

    remaining_executions = status_response.remaining_executions
    if remaining_executions:
        if len(remaining_executions) == 1:
            logger.info(
                'Cloudify Manager currently has one '
                'running or pending execution. Waiting for it'
                ' to finish before entering maintenance mode.')
        else:
            logger.info(
                'Cloudify Manager currently has {0} '
                'running or pending executions. Waiting for all '
                'executions to finish before entering maintenance '
                'mode.'.format(
                    len(remaining_executions)))

        if get_global_verbosity() != NO_VERBOSE:
            print_data(
                columns=EXECUTION_COLUMNS,
                items=remaining_executions,
                header_text='Remaining executions:',
                max_width=50
            )

    if status_response.status == MAINTENANCE_MODE_ACTIVE:
        logger.info('INFO - Cloudify Manager is currently in maintenance '
                    'mode. Most requests will be blocked.\n')


@maintenance_mode.command(name='activate',
                          short_help='Activate maintenance-mode '
                          '[manager only]')
@cfy.options.wait
@cfy.options.timeout(default=0)
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def activate(wait, timeout, logger, client):
    """Enter maintenance-mode on the manager rejecting further REST requests.
    """

    if timeout and not wait:
        msg = "'--timeout' was used without '--wait'."
        error = exceptions.CloudifyCliError(msg)
        error.possible_solutions = [
            "Add the '--wait' flag to the command in order to wait."
        ]
        raise error

    logger.info('Entering maintenance mode...')
    client.maintenance_mode.activate()

    if wait:
        logger.info("Cloudify manager will enter Maintenance mode once "
                    "there are no running or pending executions...\n")
        deadline = time.time() + timeout

        while True:
            if _is_timeout(timeout, deadline):
                raise exceptions.CloudifyCliError(
                    "Timed out while entering maintenance mode. "
                    "Note that the manager is still entering maintenance mode"
                    " in the background. You can run "
                    "'cfy maintenance-mode status' to check the status.")

            status_response = client.maintenance_mode.status()
            if status_response.status == MAINTENANCE_MODE_ACTIVE:
                logger.info('Manager is in maintenance mode.')
                logger.info('While in maintenance mode most requests will '
                            'be blocked.')
                return
            time.sleep(DEFAULT_TIMEOUT_INTERVAL)
    logger.info("Run 'cfy maintenance-mode status' to check the "
                "maintenance mode's status.\n")


@maintenance_mode.command(name='deactivate',
                          short_help='Deactivate maintenance-mode '
                          '[manager only]')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def deactivate(logger, client):
    """Deactivate maintenance-mode on the manager to accept REST requests.
    """
    logger.info('Turning off maintenance mode...')
    client.maintenance_mode.deactivate()
    logger.info('Maintenance mode is off.')


def _is_timeout(timeout, deadline):
    return timeout > 0 and time.time() > deadline
