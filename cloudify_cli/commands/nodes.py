########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from cloudify_rest_client.exceptions import CloudifyClientError

from .. import utils
from .. import common
from ..config import cfy
from ..exceptions import CloudifyCliError


@cfy.group(name='nodes')
@cfy.options.verbose
@cfy.assert_manager_active
def nodes():
    """Handle a deployment's nodes
    """
    pass


@nodes.command(name='get',
               short_help='Retrieve node information [manager only]')
@cfy.argument('node-id')
@cfy.options.deployment_id(required=True)
@cfy.options.verbose
@cfy.add_logger
@cfy.add_client()
def get(node_id, deployment_id, logger, client):
    """Retrieve information for a specific node of a specific deployment

    `NODE_ID` is the node id to get information on.
    """
    logger.info('Retrieving node {0} for deployment {1}'.format(
        node_id, deployment_id))
    try:
        node = client.nodes.get(deployment_id, node_id)
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Node {0} was not found'.format(node_id))

    logger.debug('Getting node instances for node with ID \'{0}\''
                 .format(node_id))
    try:
        instances = client.node_instances.list(deployment_id, node_id)
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise

    # print node parameters
    columns = ['id', 'deployment_id', 'blueprint_id', 'host_id', 'type',
               'number_of_instances', 'planned_number_of_instances']
    pt = utils.table(columns, data=[node])
    pt.max_width = 50
    common.print_table('Node:', pt)

    # print node properties
    logger.info('Node properties:')
    for property_name, property_value in utils.decode_dict(
            node.properties).iteritems():
        logger.info('\t{0}: {1}'.format(property_name, property_value))
    logger.info('')

    # print node instances IDs
    logger.info('Node instance IDs:')
    if instances:
        for instance in instances:
            logger.info('\t{0}'.format(instance['id']))
    else:
        logger.info('\tNo node instances')


@nodes.command(name='list',
               short_help='List nodes for a deployment '
               '[manager only]')
@cfy.options.deployment_id()
@cfy.options.sort_by('deployment_id')
@cfy.options.descending
@cfy.options.verbose
@cfy.add_logger
@cfy.add_client()
def list(deployment_id, sort_by, descending, logger, client):
    """List nodes

    If `DEPLOYMENT_ID` is provided, list nodes for that deployment.
    Otherwise, list nodes for all deployments.
    """
    try:
        if deployment_id:
            logger.info('Listing nodes for deployment {0}...'.format(
                deployment_id))
        else:
            logger.info('Listing all nodes...')
        nodes = client.nodes.list(
            deployment_id=deployment_id,
            sort=sort_by,
            is_descending=descending)
    except CloudifyClientError as e:
        if not e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} does not exist'.format(
            deployment_id))

    columns = ['id', 'deployment_id', 'blueprint_id', 'host_id', 'type',
               'number_of_instances', 'planned_number_of_instances']
    pt = utils.table(columns, data=nodes)
    common.print_table('Nodes:', pt)
