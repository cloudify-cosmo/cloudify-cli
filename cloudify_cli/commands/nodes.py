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
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
#    * limitations under the License.

"""
Handles all commands that start with 'cfy nodes'
"""

from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_cli import utils
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.logger import get_logger


def get(node_id, deployment_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    try:
        logger.info('Getting node: '
                    '\'{0}\' for deployment with ID \'{1}\' [manager={2}]'
                    .format(node_id, deployment_id, management_ip))
        node = client.nodes.get(deployment_id, node_id)
    except CloudifyClientError, e:
        if e.status_code != 404:
            raise
        msg = ("Node with ID '{0}' was not found on the management server"
               .format(node_id))
        raise CloudifyCliError(msg)
    columns = ['id', 'type', 'number_of_instances',
               'planned_number_of_instances']
    pt = utils.table(columns, [node])
    pt.max_width = 50
    utils.print_table('Node:', pt)


def ls(deployment_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)
    try:
        if deployment_id:
            logger.info('Getting executions list for deployment: \'{0}\' '
                        '[manager={1}]'.format(deployment_id, management_ip))
        else:
            logger.info(
                'Getting a list of all executions: [manager={0}]'.format(
                    management_ip))
        nodes = client.nodes.list(deployment_id=deployment_id)
    except CloudifyClientError, e:
        if not e.status_code != 404:
            raise
        msg = ('Deployment {0} does not exist on management server'
               .format(deployment_id))
        raise CloudifyCliError(msg)

    columns = ['id', 'type', 'number_of_instances',
               'planned_number_of_instances']
    pt = utils.table(columns, nodes)
    utils.print_table('Nodes:', pt)
