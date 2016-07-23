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

import json

from cloudify_rest_client.exceptions import CloudifyClientError

from .. import env
from .. import utils
from .. import common
from ..config import cfy
from ..logger import get_logger
from ..exceptions import CloudifyCliError


@cfy.group(name='node-instances')
@cfy.options.verbose
def manager():
    """Handle a deployment's node-instances
    """
    env.assert_manager_active()


@manager.command(name='get')
@cfy.argument('node_instance_id')
@cfy.options.verbose
def get(node_instance_id):
    """Retrieve information for a specific node-instance

    `NODE_INSTANCE_ID` is the id of the node-instance to get information on.
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Retrieving node instance {0}'.format(node_instance_id))
    try:
        node_instance = client.node_instances.get(node_instance_id)
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Node instance {0} not found'.format(
            node_instance_id))

    columns = ['id', 'deployment_id', 'host_id', 'node_id', 'state']
    pt = utils.table(columns, [node_instance])
    pt.max_width = 50
    common.print_table('Instance:', pt)

    # print node instance runtime properties
    logger.info('Instance runtime properties:')
    for prop_name, prop_value in utils.decode_dict(
            node_instance.runtime_properties).iteritems():
        logger.info('\t{0}: {1}'.format(prop_name, prop_value))
    logger.info('')


@manager.command(name='list')
@cfy.options.deployment_id(required=False)
@cfy.options.node_name
@cfy.options.verbose
def list(deployment_id, node_name):
    """List node-instances

    If `DEPLOYMENT_ID` is provided, list node-instances for that deployment.
    Otherwise, list node-instances for all deployments.
    """
    logger = get_logger()
    client = env.get_rest_client()

    try:
        if deployment_id:
            logger.info('Listing instances for deployment {0}...'.format(
                deployment_id))
        else:
            logger.info('Listing all instances...')
        instances = client.node_instances.list(deployment_id=deployment_id,
                                               node_name=node_name)
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} does not exist'.format(
            deployment_id))

    columns = ['id', 'deployment_id', 'host_id', 'node_id', 'state']
    pt = utils.table(columns, instances)
    common.print_table('Instances:', pt)


@cfy.command(name='node-instances')
@cfy.argument('node-id', required=False)
@cfy.options.verbose
def local(node_id):
    """Display node-instances for the execution

    `NODE_ID` is id of the node to list instances for.
    """
    logger = get_logger()

    env = common.load_env()
    node_instances = env.storage.get_node_instances()
    if node_id:
        node_instances = [instance for instance in node_instances
                          if instance.node_id == node_id]
        if not node_instances:
            raise exceptions.CloudifyCliError(
                'Could not find node {0}'.format(node_id))
    logger.info(json.dumps(node_instances, sort_keys=True, indent=2))
