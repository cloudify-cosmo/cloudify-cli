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

import click

from cloudify_rest_client.exceptions import CloudifyClientError

from .. import utils
from .. import common
from ..config import cfy
from ..logger import get_logger
from ..exceptions import CloudifyCliError


@cfy.group(name='node-instances')
def manager():
    """Handle a deployment's node-instances
    """
    pass


@manager.command(name='get')
@click.argument('node_instance_id', required=True)
def get(node_instance_id):
    """Retrieve information for a specific node-instance
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info('Retrieving node instance {0}'.format(node_instance_id))
    try:
        node_instance = client.node_instances.get(node_instance_id)
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Node instance {0} not found')

    columns = ['id', 'deployment_id', 'host_id', 'node_id', 'state']
    pt = utils.table(columns, [node_instance])
    pt.max_width = 50
    utils.print_table('Instance:', pt)

    # print node instance runtime properties
    logger.info('Instance runtime properties:')
    for prop_name, prop_value in utils.decode_dict(
            node_instance.runtime_properties).iteritems():
        logger.info('\t{0}: {1}'.format(prop_name, prop_value))
    logger.info('')


@manager.command(name='ls')
@click.argument('deployment-id', required=False)
@cfy.options.node_name
def ls(deployment_id, node_name):
    """List node-instances

    If `DEPLOYMENT_ID` is provided, list node-instances for that deployment.
    Else, list node-instances for all deployments.
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)
    try:
        if deployment_id:
            logger.info('Listing instances for deployment {0}...'.format(
                deployment_id))
        else:
            logger.info('Listing all instances...')
        instances = client.node_instances.list(deployment_id=deployment_id,
                                               node_name=node_name)
    except CloudifyClientError as e:
        if not e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} does not exist'.format(
            deployment_id))

    columns = ['id', 'deployment_id', 'host_id', 'node_id', 'state']
    pt = utils.table(columns, instances)
    utils.print_table('Instances:', pt)


@cfy.command(name='node-instances')
@click.argument('node-id', required=False)
def local(node_id):
    """Display node-instances for the execution
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
