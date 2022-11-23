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

import json

from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_cli import utils
from cloudify_cli.cli import cfy, helptexts
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.local import load_env
from cloudify_cli.logger import get_global_json_output
from cloudify_cli.table import print_data, print_details, print_single
from cloudify_cli.utils import deep_update_dict, deep_subtract_dict
from cloudify_cli.commands.summary import (
    BASE_SUMMARY_FIELDS,
    structure_summary_results)


NODE_INSTANCE_COLUMNS = ['id', 'deployment_id', 'host_id', 'node_id', 'state',
                         'visibility', 'tenant_name', 'created_by']
NODE_INSTANCES_SUMMARY_FIELDS = [
    'deployment_id',
    'node_id',
    'state',
    'host_id',
] + BASE_SUMMARY_FIELDS


@cfy.group(name='node-instances')
@cfy.options.common_options
@cfy.assert_manager_active()
def node_instances():
    """Handle a deployment's node-instances
    """
    pass


@node_instances.command(name='get',
                        short_help='Retrieve node-instance information '
                                   '[manager only]')
@cfy.argument('node_instance_id')
@cfy.options.common_options
@cfy.options.tenant_name(
    required=False, resource_name_for_help='node-instance')
@cfy.options.evaluate_functions
@cfy.pass_logger
@cfy.pass_client()
@cfy.options.extended_view
def get(node_instance_id, evaluate_functions, logger, client, tenant_name):
    """Retrieve information for a specific node-instance

    `NODE_INSTANCE_ID` is the id of the node-instance to get information on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving node instance %s', node_instance_id)
    try:
        node_instance = client.node_instances.get(
            node_instance_id,
            evaluate_functions=evaluate_functions,
        )
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Node instance {0} not found'.format(
            node_instance_id))

    _print_node_instance(node_instance)
    logger.info('')


@node_instances.command(name='list',
                        short_help='List node-instances for a deployment '
                                   '[manager only]')
@cfy.options.deployment_id(required=False)
@cfy.options.node_name
@cfy.options.sort_by('node_id')
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='node-instance')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.pass_logger
@cfy.pass_client()
@cfy.options.extended_view
def list(deployment_id,
         node_name,
         sort_by,
         descending,
         all_tenants,
         search,
         pagination_offset,
         pagination_size,
         logger,
         client,
         tenant_name):
    """List node-instances

    If `DEPLOYMENT_ID` is provided, list node-instances for that deployment.
    Otherwise, list node-instances for all deployments.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    try:
        if deployment_id:
            logger.info('Listing instances for deployment {0}...'.format(
                deployment_id))
        else:
            logger.info('Listing all instances...')
        node_instances = client.node_instances.list(
            deployment_id=deployment_id,
            node_name=node_name,
            sort=sort_by,
            is_descending=descending,
            _all_tenants=all_tenants,
            _search=search,
            _offset=pagination_offset,
            _size=pagination_size)
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} does not exist'.format(
            deployment_id))

    print_data(NODE_INSTANCE_COLUMNS, node_instances, 'Node-instances:')
    total = node_instances.metadata.pagination.total
    logger.info('Showing {0} of {1} node-instances'
                .format(len(node_instances), total))


@node_instances.command(name='summary',
                        short_help='Retrieve summary of node instance '
                                   'details [manager only]',
                        help=helptexts.SUMMARY_HELP.format(
                            type='node-instances',
                            example='node instance with the same '
                                    'deployment ID',
                            fields='|'.join(NODE_INSTANCES_SUMMARY_FIELDS)))
@cfy.argument('target_field',
              type=cfy.SummaryArgs(NODE_INSTANCES_SUMMARY_FIELDS))
@cfy.argument('sub_field',
              type=cfy.SummaryArgs(NODE_INSTANCES_SUMMARY_FIELDS),
              default=None, required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def summary(target_field, sub_field, logger, client, tenant_name,
            all_tenants):
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info(
        'Retrieving summary of node instances on field {field}'.format(
            field=target_field,
        )
    )

    summary = client.summary.node_instances.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
    )

    columns, items = structure_summary_results(
        summary.items,
        target_field,
        sub_field,
        'node_instances',
    )

    print_data(
        columns,
        items,
        'Node instance summary by {field}'.format(field=target_field),
    )


@node_instances.command(name='update-runtime',
                        short_help='Update runtime properties of a '
                                   'node-instance [manager only]')
@cfy.argument('node_instance_id')
@cfy.options.common_options
@cfy.options.runtime_properties
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='node-instance')
@cfy.pass_logger
@cfy.pass_client()
@cfy.options.extended_view
def update_runtime(node_instance_id, logger, client, tenant_name, properties):
    """Update the runtime properties of a specific node-instance

    `NODE_INSTANCE_ID` is the id of the node-instance to update.
    """
    _modify_runtime(node_instance_id, logger, client, tenant_name,
                    properties, deep_update_dict)


@node_instances.command(name='delete-runtime',
                        short_help='Delete runtime properties of a '
                                   'node-instance [manager only]')
@cfy.argument('node_instance_id')
@cfy.options.common_options
@cfy.options.runtime_properties
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='node-instance')
@cfy.pass_logger
@cfy.pass_client()
@cfy.options.extended_view
def delete_runtime(node_instance_id, logger, client, tenant_name, properties):
    """Delete specified runtime properties of a specific node-instance

    `NODE_INSTANCE_ID` is the id of the node-instance to update.
    """
    _modify_runtime(node_instance_id, logger, client, tenant_name,
                    properties, deep_subtract_dict)


def _modify_runtime(node_instance_id, logger, client, tenant_name,
                    properties, modifier_function):
    """Update or delete the runtime properties of a specific node-instance"""
    utils.explicit_tenant_name_message(tenant_name, logger)
    node_instance = client.node_instances.get(node_instance_id)

    runtime_properties = node_instance.runtime_properties
    modifier_function(runtime_properties, properties)
    new_version = node_instance.version + 1

    client.node_instances.update(node_instance_id,
                                 runtime_properties=runtime_properties,
                                 version=new_version)
    logger.info('Successfully updated the runtime properties of "{0}"'
                .format(node_instance_id))
    node_instance = client.node_instances.get(node_instance_id)
    _print_node_instance(node_instance)


@cfy.command(name='node-instances',
             short_help='Show node-instance information [locally]')
@cfy.argument('node-id', required=False)
@cfy.options.blueprint_id(required=True)
@cfy.options.common_options
@cfy.pass_logger
def local(node_id, blueprint_id, logger):
    """Display node-instances for the execution

    `NODE_ID` is id of the node to list instances for.
    """
    env = load_env(blueprint_id)
    node_instances = env.storage.get_node_instances()
    if node_id:
        node_instances = [instance for instance in node_instances
                          if instance.node_id == node_id]
        if not node_instances:
            raise CloudifyCliError(
                'Could not find node {0}'.format(node_id))
    logger.info(json.dumps(node_instances, sort_keys=True, indent=2))


def _print_node_instance(node_instance):
    if get_global_json_output():
        # For json output, make sure the properties are in the same object
        # so that the output is a single decode-able object
        columns = NODE_INSTANCE_COLUMNS + \
            ['runtime_properties', 'system_properties']
        print_single(columns, node_instance, 'Node-instance:', 50)
    else:
        print_single(NODE_INSTANCE_COLUMNS, node_instance,
                     'Node-instance:', 50)

        print_details(node_instance.runtime_properties,
                      'Instance runtime properties:')

        if hasattr(node_instance, 'system_properties'):
            print_details(node_instance.system_properties,
                          'Instance system properties:')
