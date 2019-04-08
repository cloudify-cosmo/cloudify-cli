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

from functools import wraps

from requests.exceptions import ConnectionError

from .. import env
from ..cli import cfy
from ..table import print_data
from ..exceptions import CloudifyCliError


# The list will be updated with the services on each manager
CLUSTER_COLUMNS = ['hostname', 'private_ip', 'public_ip', 'version', 'edition',
                   'distribution', 'distro_release', 'status']


def pass_cluster_client(*client_args, **client_kwargs):
    """
    Pass the REST client, and assert that it is connected to a cluster.

    Instead of using `@cfy.pass_client()`, use this function for an automatic
    check that we're using a cluster.
    """
    def _deco(f):
        @cfy.pass_client(*client_args, **client_kwargs)
        @wraps(f)
        def _inner(client, *args, **kwargs):
            managers_list = client.manager.get_managers().items
            if len(managers_list) == 1:
                raise CloudifyCliError('This manager is not part of a '
                                       'Cloudify Manager cluster')
            return f(client=client, *args, **kwargs)
        return _inner
    return _deco


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
@pass_cluster_client()
@cfy.options.common_options
def status(client):
    """
    Display the current status of the Cloudify Manager cluster
    """
    managers = client.manager.get_managers().items
    updated_columns = CLUSTER_COLUMNS
    for manager in managers:
        client.host = manager.public_ip
        try:
            services = client.manager.get_status()['services']
            updated_columns += [
                service['display_name'].ljust(20) for service in services
                if service['display_name'].ljust(20) not in updated_columns
            ]
            manager.update({'status': 'Active'})
        except ConnectionError:
            manager.update({'status': 'Offline'})
            continue
        for service in services:
            state = service['instances'][0]['state'] \
                if 'instances' in service and \
                   len(service['instances']) > 0 else 'unknown'
            manager.update({service['display_name'].ljust(20): state})
    print_data(updated_columns, managers, 'HA Cluster nodes')


@cluster.command(name='remove',
                 short_help='Remove a node from the cluster [cluster only]')
@pass_cluster_client()
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
                     for node in client.manager.get_managers().items}
    if hostname not in cluster_nodes:
        raise CloudifyCliError('Invalid command. {0} is not a member of '
                               'the cluster.'.format(hostname))

    client.manager.remove_manager(hostname)

    logger.info('Node {0} was removed successfully!'
                .format(hostname))


@cluster.command(name='update-profile',
                 short_help='Store the cluster nodes in the CLI profile '
                            '[cluster only]')
@pass_cluster_client()
@cfy.pass_logger
@cfy.options.common_options
def update_profile(client, logger):
    """
    Fetch the list of the cluster nodes and update the current profile.

    Use this to update the profile if nodes are added to the cluster from
    another machine. Only the cluster nodes that are stored in the profile
    will be contacted in case of a manager failure.
    """
    logger.info('Fetching the cluster nodes list...')
    nodes = client.manager.get_managers().items
    _update_profile_cluster_settings(nodes, logger=logger)
    logger.info('Profile is up to date with {0} nodes'
                .format(len(env.profile.cluster)))


def _update_profile_cluster_settings(nodes, logger=None):
    """
    Update the cluster list set in profile with the received nodes

    We will merge the received nodes into the stored list - adding and
    removing when necessary - and not just set the profile list to the
    received nodes, because the profile might have more details about
    the nodes (eg. a certificate path)
    """
    stored_nodes = {node.get('hostname') for node in env.profile.cluster}
    received_nodes = {node.hostname for node in nodes}
    if env.profile.cluster is None:
        env.profile.cluster = []
    for node in nodes:
        if node.hostname not in stored_nodes:
            node_ip = node.public_ip or node.private_ip
            if logger:
                logger.info('Adding cluster node {0} to local profile'
                            .format(node_ip))
            env.profile.cluster.append({
                'hostname': node.hostname,
                # all other connection parameters will be defaulted to the
                # ones from the last used manager
                'manager_ip': node_ip
            })
    # filter out removed nodes
    env.profile.cluster = [n for n in env.profile.cluster
                           if n['hostname'] in received_nodes]
    env.profile.save()
