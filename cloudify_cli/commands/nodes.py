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

import click
from cloudify_rest_client.exceptions import CloudifyClientError

from .. import utils
from ..cli import cfy
from ..table import print_data, print_single, print_details
from ..exceptions import CloudifyCliError
from ..logger import get_global_json_output
from .summary import BASE_SUMMARY_FIELDS, structure_summary_results

NODE_COLUMNS = ['id', 'deployment_id', 'blueprint_id', 'host_id', 'type',
                'visibility', 'tenant_name', 'actual_number_of_instances',
                'actual_planned_number_of_instances', 'created_by']

OPERATION_COLUMNS = ['name', 'inputs', 'plugin', 'executor', 'operation']
NODE_TABLE_LABELS = {
    'actual_number_of_instances': 'number_of_instances',
    'actual_planned_number_of_instances': 'planned_number_of_instances'
}
NODES_SUMMARY_FIELDS = [
    'deployment_id',
] + BASE_SUMMARY_FIELDS


@cfy.group(name='nodes')
@cfy.options.common_options
@cfy.assert_manager_active()
def nodes():
    """Handle a deployment's nodes
    """
    pass


@nodes.command(name='get',
               short_help='Retrieve node information [manager only]')
@cfy.argument('node-id')
@cfy.options.deployment_id(required=True)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='node')
@cfy.pass_logger
@cfy.pass_client()
def get(node_id, deployment_id, logger, client, tenant_name):
    """Retrieve information for a specific node of a specific deployment

    `NODE_ID` is the node id to get information on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
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
        instances = client.node_instances.list(
            deployment_id=deployment_id,
            node_id=node_id
        )
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('No node instances were found for '
                               'node {0}'.format(node_id))

    columns = NODE_COLUMNS
    if get_global_json_output():
        columns += ['properties', 'instances', 'operations', 'type_hierarchy']
        node['instances'] = [instance['id'] for instance in instances]

    print_single(columns, node, 'Node:', max_width=50)

    if not get_global_json_output():
        # Print type hierarchy
        logger.info('Type hierarchy:\n\t{0}\n'.format('\n\t'.join(
            node.type_hierarchy)))

        # print node properties
        print_details(node.properties, 'Node properties:')

        operations = []
        for op_name, op in node.operations.items():
            # operations is a tuple (operation_name, dict_of_attributes)
            # we want to add the name to the dict
            # and build a new array in order to print it in a table
            op['name'] = op_name
            operations += [op]
        print_data(OPERATION_COLUMNS, operations, 'Operations:')

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
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='node')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.pass_logger
@cfy.pass_client()
def list(deployment_id,
         sort_by,
         descending,
         tenant_name,
         all_tenants,
         search,
         pagination_offset,
         pagination_size,
         logger, client):
    """List nodes

    If `DEPLOYMENT_ID` is provided, list nodes for that deployment.
    Otherwise, list nodes for all deployments.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    try:
        if deployment_id:
            logger.info('Listing nodes for deployment {0}...'.format(
                deployment_id))
        else:
            logger.info('Listing all nodes...')
        nodes = client.nodes.list(
            deployment_id=deployment_id,
            sort=sort_by,
            is_descending=descending,
            _all_tenants=all_tenants,
            _search=search,
            _offset=pagination_offset,
            _size=pagination_size
        )
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} does not exist'.format(
            deployment_id))

    print_data(NODE_COLUMNS, nodes, 'Nodes:', labels=NODE_TABLE_LABELS)
    total = nodes.metadata.pagination.total
    logger.info('Showing {0} of {1} nodes'.format(len(nodes), total))


@nodes.command(name='summary',
               short_help='Retrieve summary of node details [manager only]')
@cfy.argument('target_field', type=click.Choice(NODES_SUMMARY_FIELDS))
@cfy.argument('sub_field', type=click.Choice(NODES_SUMMARY_FIELDS),
              default=None, required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def summary(target_field, sub_field, logger, client, tenant_name, all_tenants):
    """Retrieve summary of nodes, e.g. a count of each node with the same
    deployment ID.

    `TARGET_FIELD` is the field to summarise nodes on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of nodes on field {field}'.format(
        field=target_field))

    summary = client.summary.nodes.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
    )

    columns, items = structure_summary_results(
        summary.items,
        target_field,
        sub_field,
        'nodes',
    )

    print_data(
        columns,
        items,
        'Node summary by {field}'.format(field=target_field),
    )
