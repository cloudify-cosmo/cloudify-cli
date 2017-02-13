########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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


import time
from datetime import datetime

from cloudify_rest_client.exceptions import (CloudifyClientError,
                                             NotClusterMaster)

from .. import env
from ..cli import cfy
from ..table import print_data
from ..exceptions import CloudifyCliError
from ..execution_events_fetcher import WAIT_FOR_EXECUTION_SLEEP_INTERVAL


CLUSTER_COLUMNS = ['name', 'host_ip', 'master', 'online']


def _verify_not_in_cluster(client):
    """Check that the current manager doesn't already belong to a cluster
    """
    status = client.cluster.status()
    if status.initialized:
        raise CloudifyCliError('This manager machine is already part '
                               'of a Cloudify Manager cluster')


@cfy.group(name='cluster')
@cfy.options.verbose()
@cfy.assert_manager_active()
def cluster():
    """Handle the Cloudify Manager cluster
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@cluster.command(name='status',
                 short_help='Show the current cluster status [cluster only]')
@cfy.pass_client()
@cfy.pass_logger
def status(client, logger):
    """Display the current status of the Cloudify Manager cluster
    """
    status = client.cluster.status()
    if not status.initialized:
        logger.error('This manager is not part of a Cloudify Manager cluster')
    else:
        logger.info('Cloudify Manager cluster initialized!\n'
                    'Encryption key: {0}'.format(status.encryption_key))


@cluster.command(name='start',
                 short_help='Start a Cloudify Manager cluster [manager only]')
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.timeout()
@cfy.options.cluster_host_ip
@cfy.options.cluster_node_name
@cfy.options.cluster_encryption_key
def start(client,
          logger,
          timeout,
          cluster_host_ip,
          cluster_node_name,
          cluster_encryption_key):
    """Start a Cloudify Manager cluster with the current manager as the master.

    This will initialize all the Cloudify Manager cluster components on the
    current manager, and mark it as the master. After that, other managers
    will be able to join the cluster by passing this manager's IP address
    and encryption key.
    """
    _verify_not_in_cluster(client)

    logger.info('Creating a new Cloudify Manager cluster')

    client.cluster.start(
        host_ip=cluster_host_ip,
        node_name=cluster_node_name,
        encryption_key=cluster_encryption_key
    )
    status = _wait_for_cluster_initialized(client, logger, timeout=timeout)

    if status.error:
        logger.error('Error while configuring the Cloudify Manager cluster')
        raise CloudifyCliError(status.error)

    _init_cluster_profile()

    logger.info('Cloudify Manager cluster started at {0}.\n'
                .format(cluster_host_ip))


@cluster.command(name='join',
                 short_help='Join a Cloudify Manager cluster [manager only]')
@cfy.pass_client()
@cfy.pass_logger
@cfy.argument('join_profile')
@cfy.options.timeout()
@cfy.options.cluster_host_ip
@cfy.options.cluster_node_name
def join(client,
         logger,
         join_profile,
         timeout,
         cluster_host_ip,
         cluster_node_name):
    """Join a Cloudify Manager cluster on this manager.

    A cluster with at least one machine needs to already exist.
    Pass the address of at least one member of the cluster as --cluster-join
    Specifying multiple addresses - even all members of the cluster - is
    encouraged, as it will allow to join the cluster even if some of the
    current members are unreachable, but is not required.
    """
    _verify_not_in_cluster(client)
    if not env.is_profile_exists(join_profile):
        raise CloudifyCliError('No such profile: {0}'
                               .format(join_profile))
    joined_profile = env.get_profile_context(join_profile)
    if not joined_profile.cluster:
        raise CloudifyCliError('Cannot join profile {0} - that profile '
                               'has no cluster started'
                               .format(join_profile))

    deadline = time.time() + timeout
    cluster_client = env.get_rest_client(
        rest_host=joined_profile.manager_ip,
        rest_port=joined_profile.rest_port,
        rest_protocol=joined_profile.rest_protocol,
        username=joined_profile.manager_username,
        password=joined_profile.manager_password)
    cluster_status = cluster_client.cluster.status()

    encryption_key = cluster_status.encryption_key
    join = [n.host_ip for n in cluster_client.cluster.nodes.list()]
    logger.info('Joining the Cloudify Manager cluster: {0}'
                .format(join))

    client.cluster.join(
        host_ip=cluster_host_ip,
        node_name=cluster_node_name,
        encryption_key=encryption_key,
        join_addrs=join
    )
    timeout_left = deadline - time.time()
    try:
        status = _wait_for_cluster_initialized(client, logger,
                                               timeout=timeout_left)
    except NotClusterMaster:
        # current node has joined the cluster and has blocked REST requests;
        # for further status updates, we can query the cluster nodes endpoint
        # on the master
        logger.info('Node joined the cluster, waiting for database replication'
                    ' to be established')
    else:
        if status.error:
            logger.error('Error while joining the Cloudify Manager cluster')
            raise CloudifyCliError(status.error)

    while True:
        if time.time() > deadline:
            raise CloudifyCliError('Timed out waiting for database '
                                   'replication to be established')

        # find the current node in the cluster nodes list, and check if it
        # reports being online
        nodes = cluster_client.cluster.nodes.list()
        joined_node = next((
            n for n in nodes
            if n.host_ip == cluster_host_ip), None)
        if joined_node is not None and joined_node.online:
            break
        else:
            time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)

    node = _make_node_from_profile()
    joined_profile.cluster.append(node)
    joined_profile.save()

    logger.info('Cloudify Manager cluster joined successfully!')
    logger.info('Switching to the cluster profile: {0}'.format(join_profile))

    env.set_active_profile(join_profile)


@cluster.command(name='update-profile',
                 short_help='Store the cluster nodes in the CLI profile '
                            '[cluster only')
@cfy.pass_client()
@cfy.pass_logger
def update_profile(client,
                   logger):
    """Fetch the list of the cluster nodes and update the current profile.

    Use this to update the profile if nodes are added to the cluster from
    another machine. Only the cluster nodes that are stored in the profile
    will be contacted in case of a cluster master failure.
    """
    logger.info('Fetching the cluster nodes list...')
    nodes = client.cluster.nodes.list()
    stored_nodes = {node['manager_ip'] for node in env.profile.cluster}
    for node in nodes:
        if node.host_ip not in stored_nodes:
            logger.info('Adding cluster node: {0}'.format(node.host_ip))
            env.profile.cluster.append({
                # currently only the host IP is received; all other parameters
                # will be defaulted to the ones from the last used manager
                'manager_ip': node.host_ip
            })
    env.profile.save()
    logger.info('Profile is up to date with {0} nodes'
                .format(len(env.profile.cluster)))


@cluster.group(name='nodes')
def nodes():
    """Handle the cluster nodes [cluster only]
    """


@nodes.command(name='list',
               short_help='List the nodes in the cluster [cluster only]')
@cfy.pass_client()
@cfy.pass_logger
def list_nodes(client, logger):
    """Display a table with basic information about the nodes in the cluster
    """
    response = client.cluster.nodes.list()
    default = {'master': False, 'online': False}
    print_data(CLUSTER_COLUMNS, response, 'HA Cluster nodes', defaults=default)


@nodes.command(name='remove',
               short_help='Remove a node from the cluster [cluster only]')
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.cluster_node_name
def remove_node(client, logger, cluster_node_name):
    """Unregister a node from the cluster.

    Note that this will not teardown the removed node, only remove it from
    the cluster. Removed replicas are not usable as Cloudify Managers,
    so it is left to the user to examine and teardown the node.
    """
    cluster_nodes = {node['name']: node.host_ip
                     for node in client.cluster.nodes.list()}

    if cluster_node_name not in cluster_nodes:
        raise CloudifyCliError('{0} is not a member of the cluster!'
                               .format(cluster_node_name))
    removed_ip = cluster_nodes[cluster_node_name]

    client.cluster.nodes.delete(cluster_node_name)

    env.profile.cluster = [node for node in env.profile.cluster
                           if node['manager_ip'] != removed_ip]
    env.profile.save()
    logger.info('Node {0} was removed successfully!')


def _make_node_from_profile():
    return {node_attr: getattr(env.profile, node_attr)
            for node_attr in env.CLUSTER_NODE_ATTRS}


def _init_cluster_profile():
    """Set the current profile as connected to a Cloudify Manager cluster.
    """
    env.profile.cluster = [_make_node_from_profile()]
    env.profile.save()


def _display_logs(logger, logs):
    for log in logs:
        timestamp = datetime.utcfromtimestamp(log['timestamp'] // 1e6)
        logger.info('{0} {1}'.format(timestamp.isoformat(),
                                     log['message']))


def _wait_for_cluster_initialized(client, logger=None, timeout=900):
    # this is similar to how an execution's logs and status are fetched,
    # but is using a different backend mechanism
    include = None
    if logger is not None:
        # only fetch logs when the logger is present - no need otherwise
        include = ['logs', 'initialized', 'error']

    # each log message will have a "cursor" value - we need to tell the server
    # what's the latest cursor position we've already seen, so that it'll only
    # yield logs more recent than that.
    last_log = None

    deadline = time.time() + timeout
    while True:
        if time.time() >= deadline:
            raise CloudifyCliError('Timed out waiting for the Cloudify '
                                   'Manager cluster to be initialized.')

        try:
            status = client.cluster.status(
                _include=include,
                since=last_log)
        except NotClusterMaster:
            raise
        except CloudifyClientError as e:
            # during cluster initialization, we restart the database, nginx,
            # and the rest service; while that happens, the server might
            # return intermittent 500 errors
            logger.info('Error while fetching cluster status: {0}'
                        .format(e))
        else:
            if logger and status.logs:
                last_log = status.logs[-1]['cursor']
                _display_logs(logger, status.logs)

            if status.initialized or status.error:
                return status

        time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)
