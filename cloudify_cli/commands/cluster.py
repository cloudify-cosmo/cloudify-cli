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
import json
from logging import warning

from requests.exceptions import ConnectionError

from .. import env
from ..cli import cfy
from ..table import print_data, print_details
from ..exceptions import CloudifyCliError
from ..logger import (
    get_global_json_output,
    get_global_verbosity,
    LOW_VERBOSE
)

from cloudify_rest_client.exceptions import CloudifyClientError


# The list will be updated with the services on each manager
CLUSTER_COLUMNS = ['hostname', 'private_ip', 'public_ip', 'version', 'edition',
                   'distribution', 'distro_release', 'status']
BROKER_COLUMNS = ['name', 'port', 'networks']


def check_manager_exists(managers, hostname, must_exist=True):
    manager_names = {manager['hostname'] for manager in managers}
    if must_exist and hostname not in manager_names:
        raise CloudifyCliError(
            '{name} is not a manager in the cluster. '
            'Current managers: {managers}'.format(
                name=hostname,
                managers=', '.join(manager_names),
            )
        )
    elif (not must_exist) and hostname in manager_names:
        raise CloudifyCliError(
            '{name} is already a manager in the cluster. '
            'Current managers: {managers}'.format(
                name=hostname,
                managers=', '.join(manager_names),
            )
        )


def check_broker_exists(brokers, name, must_exist=True):
    broker_names = {broker['name'] for broker in brokers}
    if must_exist and name not in broker_names:
        raise CloudifyCliError(
            '{name} is not a broker in the cluster. '
            'Current brokers: {brokers}'.format(
                name=name,
                brokers=', '.join(broker_names),
            )
        )
    elif (not must_exist) and name in broker_names:
        raise CloudifyCliError(
            '{name} is already a broker in the cluster. '
            'Current brokers: {brokers}'.format(
                name=name,
                brokers=', '.join(broker_names),
            )
        )


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
                warning(' It is highly recommended to have more than one '
                        'manager in a Cloudify cluster')
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
                 short_help='Show the current cluster status')
@pass_cluster_client()
@cfy.pass_logger
@cfy.options.common_options
def status(client, logger):
    """
    Display the current status of the Cloudify Manager cluster
    """
    managers = client.manager.get_managers().items
    updated_columns = CLUSTER_COLUMNS
    # After we get the managers list from either of the managers in the profile
    # we retrieve each manager's status directly
    for manager in managers:
        direct_rest_client = env.get_rest_client(
            rest_host=manager.public_ip, cluster=[])
        try:
            services = direct_rest_client.manager.get_status()['services']
            manager.update({'status': 'Active'})
            if get_global_verbosity() >= LOW_VERBOSE:
                updated_columns += [
                    display_name for display_name, service in services.items()
                    if display_name not in updated_columns
                ]
            for display_name, service in services.items():
                manager.update({display_name: service['status']})
        except (ConnectionError, CloudifyClientError) as e:
            if isinstance(e, CloudifyClientError) and e.status_code != 502:
                raise
            manager.update({'status': 'Offline'})
            continue
    print_data(updated_columns, managers, 'HA Cluster nodes')

    _list_brokers(client, logger)


@cluster.command(name='remove',
                 short_help='Remove a node from the cluster')
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
    check_manager_exists(client.manager.get_managers().items, hostname)

    client.manager.remove_manager(hostname)

    logger.info('Node {0} was removed successfully!'
                .format(hostname))


@cluster.command(name='update-profile',
                 short_help='Store the cluster nodes in the CLI profile')
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
    stored_nodes = {node['hostname'] for node in env.profile.cluster}
    received_nodes = {node['hostname'] for node in nodes}
    if env.profile.cluster is None:
        env.profile.cluster = []
    for node in nodes:
        if node['hostname'] not in stored_nodes:
            node_ip = node['public_ip'] or node['private_ip']
            if logger:
                logger.info('Adding cluster node {0} to local profile'
                            .format(node_ip))
            env.profile.cluster.append({
                'hostname': node['hostname'],
                # all other connection parameters will be defaulted to the
                # ones from the last used manager
                'manager_ip': node_ip
            })
    # filter out removed nodes
    env.profile.cluster = [n for n in env.profile.cluster
                           if n['hostname'] in received_nodes]
    env.profile.save()


@cluster.group(name='brokers',
               short_help="Handle the Cloudify Manager cluster's brokers")
@cfy.options.common_options
def brokers():
    if not env.is_initialized():
        env.raise_uninitialized()


@brokers.command(name='get',
                 short_help='Get details of a specific cluster broker')
@pass_cluster_client()
@cfy.pass_logger
@cfy.argument('name')
@cfy.options.common_options
def get_broker(client, logger, name):
    """Get full details of a specific broker associated with the cluster."""
    brokers = client.manager.get_brokers().items
    check_broker_exists(brokers, name)

    for broker in brokers:
        if broker['name'] == name:
            target_broker = broker
            break

    _clean_up_broker_for_output(target_broker)

    print_details(target_broker, 'Broker "{0}":'.format(name))


@brokers.command(name='list',
                 short_help="List the cluster's brokers")
@pass_cluster_client()
@cfy.pass_logger
@cfy.options.common_options
def list_brokers(client, logger):
    """List brokers associated with the cluster."""
    _list_brokers(client, logger)


def _clean_up_broker_for_output(broker):
    """Clean up broker details to give nicer output."""
    broker['port'] = broker['port'] or 5671
    if not get_global_json_output():
        broker['networks'] = json.dumps(broker['networks'])


def _list_brokers(client, logger):
    brokers = client.manager.get_brokers()
    for broker in brokers:
        _clean_up_broker_for_output(broker)
    print_data(BROKER_COLUMNS, brokers, 'HA Cluster brokers')


@brokers.command(name='add',
                 short_help='Add a broker to the cluster')
@pass_cluster_client()
@cfy.pass_logger
@cfy.argument('name')
@cfy.argument('address')
@cfy.options.port
@cfy.options.networks(required=False)
@cfy.options.common_options
def add_broker(client, logger, name, address, port=None, networks=None):
    """Register a broker with the cluster.

    Note that this will not create the broker itself. The broker should have
    been created before running this command.
    """
    check_broker_exists(client.manager.get_brokers().items, name,
                        must_exist=False)

    client.manager.add_broker(name, address, port, networks)

    logger.info('Broker {0} was added successfully!'
                .format(name))


@brokers.command(name='remove',
                 short_help='Remove a broker from the cluster')
@pass_cluster_client()
@cfy.pass_logger
@cfy.argument('name')
@cfy.options.common_options
def remove_broker(client, logger, name):
    """Unregister a broker from the cluster.

    Note that this will not uninstall the broker itself. The broker should be
    removed and then disassociated from the broker cluster using cfy_manager
    after being removed from the cluster.
    """
    check_broker_exists(client.manager.get_brokers().items, name)

    client.manager.remove_broker(name)

    logger.info('Broker {0} was removed successfully!'
                .format(name))


@brokers.command(name='update',
                 short_help='Update a broker in the cluster')
@pass_cluster_client()
@cfy.pass_logger
@cfy.argument('name')
@cfy.options.networks(required=True)
@cfy.options.common_options
def update_broker(client, logger, name, networks=None):
    """Update a cluster's broker's networks.

    Note that the broker must already have the appropriate certificate for the
    new networks that are being added.
    Provided networks will be added if they do not exist or updated if they
    already exist.
    Networks cannot be deleted from a broker except by removing and re-adding
    the broker.
    """
    check_broker_exists(client.manager.get_brokers().items, name)

    # When/if we support updating other parameters we can replace this check
    # with a check that at least one updatable parameter was provided.
    if not networks:
        raise CloudifyCliError(
            'Networks must be provided to update the broker.'
        )

    client.manager.update_broker(name, networks=networks)

    logger.info('Broker {0} was updated successfully!'
                .format(name))
