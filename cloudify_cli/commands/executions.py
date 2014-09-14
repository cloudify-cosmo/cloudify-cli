########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

"""
Handles all commands that start with 'cfy executions'
"""

from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli import utils
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_cli.logger import lgr


def get(execution_id):
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    try:
        lgr.info('Getting execution: '
                 '\'{0}\' [manager={1}]'.format(execution_id, management_ip))
        execution = client.executions.get(execution_id)
    except CloudifyClientError, e:
        if e.status_code != 404:
            raise
        msg = ("Execution '{0}' not found on management server"
               .format(execution_id))
        raise CloudifyCliError(msg)

    pt = utils.table(['id', 'workflow_id', 'status',
                      'created_at', 'error'],
                     [execution])
    utils.print_table('Executions:', pt)

    # print execution parameters
    lgr.info('Execution Parameters:')
    for param_name, param_value in utils.decode_dict(
            execution.parameters).iteritems():
        lgr.info('\t{0}: \t{1}'.format(param_name, param_value))
    lgr.info('')


def ls(deployment_id):
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)
    try:
        lgr.info('Getting executions list for deployment: '
                 '\'{0}\' [manager={1}]'.format(deployment_id, management_ip))
        executions = client.executions.list(deployment_id)
    except CloudifyClientError, e:
        if not e.status_code != 404:
            raise
        msg = ('Deployment {0} does not exist on management server'
               .format(deployment_id))
        raise CloudifyCliError(msg)

    pt = utils.table(['id', 'workflow_id', 'status',
                      'created_at', 'error'],
                     executions)
    utils.print_table('Executions:', pt)


def cancel(execution_id, force):
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)
    lgr.info(
        '{0}Cancelling execution {1} on management server {2}'
        .format('Force-' if force else '', execution_id, management_ip))
    client.executions.cancel(execution_id, force)
    lgr.info(
        'A cancel request for execution {0} has been sent to management '
        "server {1}. To track the execution's status, use:\n"
        "cfy executions get -e {0}"
        .format(execution_id, management_ip))
