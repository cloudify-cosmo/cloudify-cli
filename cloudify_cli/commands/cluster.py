########
# Copyright (c) 2019 Cloudify.co Ltd. All rights reserved
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

from requests.exceptions import ConnectionError

from .. import env
from ..cli import cfy
from ..table import print_data
from ..exceptions import CloudifyCliError


# The list will be updated with the services on each manager
CLUSTER_COLUMNS = ['hostname', 'private_ip', 'public_ip', 'version', 'edition',
                   'distribution', 'distro_release', 'status']


@cfy.group(name='cluster')
@cfy.options.common_options
def cluster():
    """
    Handle the Cloudify Manager cluster
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@cluster.command(name='status',
                 short_help='Show the current cluster status [cluster only]')
@cfy.options.common_options
@cfy.pass_client()
def status(client):
    """
    Display the current status of the Cloudify Manager cluster
    """
    managers = client.manager.get_managers().items
    updated_columns = []
    for manager in managers:
        client.host = manager.public_ip
        try:
            services = client.manager.get_status()['services']
            updated_columns = [] + CLUSTER_COLUMNS + [
                service['display_name'].ljust(30) for service in services
            ]
            manager.update({'status': 'Online'})
        except ConnectionError:
            manager.update({'status': 'Offline'})
            continue
        for service in services:
            state = service['instances'][0]['state'] \
                if 'instances' in service and \
                   len(service['instances']) > 0 else 'unknown'
            manager.update({service['display_name'].ljust(30): state})
    print_data(updated_columns, managers, 'HA Cluster nodes')


@cluster.command(name='remove',
                 short_help='Remove a node from the cluster [cluster only]')
@cfy.pass_logger
@cfy.argument('hostname')
@cfy.options.common_options
def remove_node(client, logger, hostname):
    """
    Unregister a node from the cluster.

    Note that this will not teardown the removed node, only remove it from
    the cluster, it will still contact the cluster's DB and RabbitMQ.
    Removed replicas are not usable as Cloudify Managers, so it is left to the
    user to examine and teardown the node.
    """
    cluster_nodes = {node['hostname']: node.public_ip
                     for node in client.manager.get_managers()}
    if hostname not in cluster_nodes:
        raise CloudifyCliError('Invalid command. {0} is not a member of '
                               'the cluster.'.format(hostname))

    client.manager.remove_manager(hostname)

    logger.info('Node {0} was removed successfully!'
                .format(hostname))
