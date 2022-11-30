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

import json
from functools import wraps

from cloudify.cluster_status import CloudifyNodeType
from cloudify_rest_client.exceptions import CloudifyClientError, \
    UserUnauthorizedError

from cloudify_cli import env
from cloudify_cli.cli import cfy
from cloudify_cli.env import profile
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.logger import (
    output,
    get_logger,
    CloudifyJSONEncoder,
    get_global_json_output
)
from cloudify_cli.table import print_data, print_details

# The list will be updated with the services on each manager
MANAGER_COLUMNS = ['hostname', 'private_ip', 'public_ip', 'version', 'edition',
                   'distribution', 'distro_release', 'last_seen', 'networks']
BROKER_COLUMNS = ['name', 'port', 'networks', 'is_external', 'host']
DB_COLUMNS = ['name', 'host', 'is_external']


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
            if _all_in_one_manager(client):
                get_logger().warning('You are trying to run cluster '
                                     'related commands on an all-in-one '
                                     'Cloudify Manager!')
            return f(client=client, *args, **kwargs)
        return _inner
    return _deco


def _all_in_one_manager(client):
    try:
        manager_nodes = client.manager.get_managers().items
        if len(manager_nodes) > 1:
            return False
        broker_nodes = client.manager.get_brokers().items
        if len(broker_nodes) > 1:
            return False
        db_nodes_items = client.manager.get_db_nodes().items
        if len(db_nodes_items) > 1:
            return False
        if len(manager_nodes) == 1:
            if len(broker_nodes) == len(db_nodes_items) == 1:
                db_node_ip = db_nodes_items[0].get('host')
                broker_node_ip = broker_nodes[0].get('host')
                manager_node_ip = manager_nodes[0].get('private_ip')
                if db_node_ip == broker_node_ip == manager_node_ip:
                    return True

            get_logger().warning('It is highly recommended to have more '
                                 'than one manager in a Cloudify cluster')
    except CloudifyClientError as e:
        if e.status_code == 404:
            get_logger().warning('Used Cloudify Manager version is lower than'
                                 ' 5.0.5 and requires a lower Cloudify CLI '
                                 'version. Please install the relevant '
                                 'Manager version\'s CLI')
            is_old_cluster = client._client.get('/cluster').get(
                'initialized', False)
            return not is_old_cluster
        else:
            raise e
    return False


@cfy.group(name='cluster')
@cfy.options.common_options
def cluster():
    """
    Handle the Cloudify Manager cluster (Premium feature)
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@cluster.command(name='status',
                 short_help='Show the current cluster status')
@pass_cluster_client()
@cfy.assert_manager_active()
@cfy.pass_logger
@cfy.options.common_options
def status(client, logger):
    """
    Display the current status of the Cloudify cluster
    """
    rest_host = profile.manager_ip
    logger.info('Retrieving Cloudify cluster status... [ip={0}]'.format(
        rest_host))
    try:
        status_result = client.cluster_status.get_status()
    except UserUnauthorizedError:
        logger.info(
            'Failed to query Cloudify cluster status: User is unauthorized')
        return False
    except CloudifyClientError as e:
        logger.info('REST service at manager {0} is not '
                    'responding! {1}'.format(rest_host, e))
        return False

    if get_global_json_output():
        output(json.dumps(status_result, cls=CloudifyJSONEncoder))
    else:
        services = []
        for service_cluster, service in status_result['services'].items():
            services.append({
                'service': service_cluster.ljust(30),
                'status': service.get('status')
            })
        logger.info('Current cluster status is {0}:'.format(
            status_result.get('status')))
        print_data(['service', 'status'], services, 'Cluster status services:')


@cluster.command(name='remove',
                 short_help='Remove a node from the cluster')
@pass_cluster_client()
@cfy.pass_logger
@cfy.argument('hostname')
@cfy.options.common_options
def remove_node(client, logger, hostname):
    """
    Unregister a Manager node from the cluster.

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
    another machine. Only the manager cluster nodes that are stored in
    the profile will be contacted in case of a manager failure.
    """
    update_profile_logic(client, logger)


def update_profile_logic(client, logger):
    """
    The logic is separated so that the function can be called
    without the Click decorators, e.g. as used in cfy profiles use
    """
    manager_nodes = client.manager.get_managers().items
    broker_nodes = client.manager.get_brokers().items
    db_nodes_items = client.manager.get_db_nodes().items
    _update_profile_cluster_settings(manager_nodes, broker_nodes,
                                     db_nodes_items, logger=logger)
    logger.info('Profile is up to date with {0} nodes'.format(
        sum([len(env.profile.cluster[key]) for key in env.profile.cluster])))


def _update_profile_cluster_settings(manager_nodes, broker_nodes,
                                     db_nodes_items, logger=None):
    """
    Update the cluster list set in profile with the received nodes

    We will merge the received nodes into the stored list - adding and
    removing when necessary - and not just set the profile list to the
    received nodes, because the profile might have more details about
    the nodes (eg. a certificate path)
    """
    env.profile.cluster = env.profile.cluster or dict()
    _update_cluster_nodes(manager_nodes, CloudifyNodeType.MANAGER, logger)
    _update_cluster_nodes(broker_nodes, CloudifyNodeType.BROKER, logger)
    _update_cluster_nodes(db_nodes_items, CloudifyNodeType.DB, logger)


def _update_cluster_nodes(nodes, nodes_type, logger):
    stored_nodes = env.profile.cluster.get(nodes_type)
    stored_nodes_names = ({_get_node_host(node) for node in stored_nodes}
                          if stored_nodes else {})
    received_nodes_names = {_get_node_host(node) for node in nodes}
    for node in nodes:
        _update_node(node, nodes_type, logger, stored_nodes_names)
    # filter out removed nodes
    env.profile.cluster[nodes_type] = [
        node for node in env.profile.cluster.get(nodes_type, {})
        if _get_node_host(node) in received_nodes_names]
    env.profile.save()


def _update_node(node, node_type, logger, stored_nodes_names):
    if _get_node_host(node) not in stored_nodes_names:
        if node_type == CloudifyNodeType.MANAGER:
            if env.profile.name == "manager-local":
                node_ip = node['private_ip']
            else:
                node_ip = node['public_ip'] or node['private_ip']
        else:
            node_ip = node['host']
        if logger:
            logger.info('Adding cluster node {0} to local profile {1} cluster'
                        .format(node_ip, node_type))
        if not env.profile.cluster.get(node_type):
            env.profile.cluster[node_type] = []
        env.profile.cluster[node_type].append({
            'hostname': _get_node_host(node),
            'host_type': node_type,
            'host_ip': node_ip
            # all other connection parameters will be defaulted to the
            # ones from the last used manager
        })


def _get_node_host(node):
    return node.get('hostname') or node.get('name')


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
@cfy.options.extended_view
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


@cluster.group(name='db-nodes',
               short_help="Handle the Cloudify DB cluster's nodes")
@cfy.options.common_options
def db_nodes():
    if not env.is_initialized():
        env.raise_uninitialized()


@db_nodes.command(name='update',
                  short_help="Make managers act upon changes to the DB nodes")
@pass_cluster_client()
@cfy.pass_logger
@cfy.options.common_options
@cfy.options.extended_view
def update_db_nodes(client, logger):
    db_nodes_list = client.manager.update_db_nodes()
    print_data(DB_COLUMNS, db_nodes_list, 'HA Cluster db nodes')


@db_nodes.command(name='list',
                  short_help="List the DB cluster's nodes")
@pass_cluster_client()
@cfy.pass_logger
@cfy.options.common_options
@cfy.options.extended_view
def list_db_nodes(client, logger):
    db_nodes_list = client.manager.get_db_nodes()
    print_data(DB_COLUMNS, db_nodes_list, 'HA Cluster db nodes')


@cluster.group(name='managers',
               short_help="Handle the Cloudify Manager cluster's nodes")
@cfy.options.common_options
def managers():
    if not env.is_initialized():
        env.raise_uninitialized()


@managers.command(name='list',
                  short_help="List the Cloudify Manager cluster's nodes")
@pass_cluster_client()
@cfy.pass_logger
@cfy.options.common_options
@cfy.options.extended_view
def list_managers(client, logger):
    managers_list = client.manager.get_managers()
    print_data(MANAGER_COLUMNS, managers_list, 'HA Cluster manager nodes')
