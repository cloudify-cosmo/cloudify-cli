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

from .. import table
from .. import utils
from ..cli import cfy
from ..local import load_env
from ..exceptions import CloudifyCliError


@cfy.group(name='node-instances')
@cfy.options.verbose()
@cfy.assert_manager_active
def manager():
    """Handle a deployment's node-instances
    """
    pass


@manager.command(name='get',
                 short_help='Retrieve node-instance information '
                 '[manager only]')
@cfy.argument('node_instance_id')
@cfy.options.verbose()
@cfy.pass_logger
@cfy.pass_client()
def get(node_instance_id, logger, client):
    """Retrieve information for a specific node-instance

    `NODE_INSTANCE_ID` is the id of the node-instance to get information on.
    """
    logger.info('Retrieving node instance {0}'.format(node_instance_id))
    try:
        node_instance = client.node_instances.get(node_instance_id)
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Node instance {0} not found'.format(
            node_instance_id))

    columns = ['id', 'deployment_id', 'host_id', 'node_id', 'state']
    pt = table.generate(columns, data=[node_instance])
    pt.max_width = 50
    table.log('Node-instance:', pt)

    # print node instance runtime properties
    logger.info('Instance runtime properties:')
    for prop_name, prop_value in utils.decode_dict(
            node_instance.runtime_properties).iteritems():
        logger.info('\t{0}: {1}'.format(prop_name, prop_value))
    logger.info('')


@manager.command(name='list',
                 short_help='List node-instances for a deployment '
                 '[manager only]')
@cfy.options.deployment_id(required=False)
@cfy.options.node_name
@cfy.options.sort_by('node_id')
@cfy.options.descending
@cfy.options.verbose()
@cfy.pass_logger
@cfy.pass_client()
def list(deployment_id, node_name, sort_by, descending, logger, client):
    """List node-instances

    If `DEPLOYMENT_ID` is provided, list node-instances for that deployment.
    Otherwise, list node-instances for all deployments.
    """
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
            is_descending=descending)
    except CloudifyClientError as e:
        if not e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} does not exist'.format(
            deployment_id))

    columns = ['id', 'deployment_id', 'host_id', 'node_id', 'state']
    pt = table.generate(columns, data=node_instances)
    table.log('Node-instances:', pt)


@cfy.command(name='node-instances',
             short_help='Show node-instance information [locally]')
@cfy.argument('node-id', required=False)
@cfy.options.blueprint_id(required=True, multiple_blueprints=True)
@cfy.options.verbose()
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
