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

import os
import time
import shutil
from functools import wraps
from datetime import datetime

from cloudify_rest_client.exceptions import (CloudifyClientError,
                                             NotClusterMaster)

from .. import constants, env
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


def pass_cluster_client(*client_args, **client_kwargs):
    """Pass the REST client, and assert that it is connected to a cluster.

    Instead of using `@cfy.pass_client()`, use this function for an automatic
    check that we're using a cluster.
    """
    def _deco(f):
        @cfy.pass_client(*client_args, **client_kwargs)
        @wraps(f)
        def _inner(client, *args, **kwargs):
            status = client.cluster.status()
            if not status.initialized:
                raise CloudifyCliError('This manager is not part of a '
                                       'Cloudify Manager cluster')
            return f(client=client, *args, **kwargs)
        return _inner
    return _deco


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
@pass_cluster_client()
@cfy.pass_logger
def status(client, logger):
    """Display the current status of the Cloudify Manager cluster
    """
    status = client.cluster.status()
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

    env.profile.profile_name = env.profile.manager_ip
    _join_node_to_profile(env.profile)

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
    cluster_client = env.get_rest_client(client_profile=joined_profile)
    cluster_status = cluster_client.cluster.status()

    encryption_key = cluster_status.encryption_key
    cluster_nodes = cluster_client.cluster.nodes.list()
    if any(n.name == cluster_node_name for n in cluster_nodes):
        raise CloudifyCliError('Node {0} is already a member of the cluster'
                               .format(cluster_node_name))
    join = [n.host_ip for n in cluster_nodes]
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
        if any(n.host_ip == cluster_host_ip for n in nodes if n.online):
            break
        else:
            time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)

    _join_node_to_profile(env.profile, joined_profile=joined_profile)
    _copy_cluster_profile_settings(from_profile=joined_profile,
                                   to_profile=env.profile)
    logger.info('Cloudify Manager joined cluster successfully.')


@cluster.command(name='update-profile',
                 short_help='Store the cluster nodes in the CLI profile '
                            '[cluster only')
@pass_cluster_client()
@cfy.pass_logger
def update_profile(client, logger):
    """Fetch the list of the cluster nodes and update the current profile.

    Use this to update the profile if nodes are added to the cluster from
    another machine. Only the cluster nodes that are stored in the profile
    will be contacted in case of a cluster master failure.
    """
    logger.info('Fetching the cluster nodes list...')
    _update_profile_cluster_settings(env.profile, client, logger=logger)
    logger.info('Profile is up to date with {0} nodes'
                .format(len(env.profile.cluster)))


def _update_profile_cluster_settings(profile, client, logger=None):
    nodes = client.cluster.nodes.list()
    stored_nodes = {node['manager_ip'] for node in env.profile.cluster}
    for node in nodes:
        if node.host_ip not in stored_nodes:
            if logger:
                logger.info('Adding cluster node: {0}'.format(node.host_ip))
            env.profile.cluster.append({
                # currently only the host IP is received; all other parameters
                # will be defaulted to the ones from the last used manager
                'manager_ip': node.host_ip
            })
    env.profile.save()


@cluster.command(name='set-active',
                 short_help='Set one of the cluster nodes as the new active '
                            '[cluster only]')
@cfy.argument('node_name')
@pass_cluster_client()
@cfy.pass_logger
def set_active(client, logger, node_name):
    nodes = client.cluster.nodes.list()
    for node in nodes:
        if node['name'] != node_name:
            continue
        if not node['online']:
            raise CloudifyCliError("Can't set node {0} as the active, "
                                   "it's offline".format(node_name))
        if node['master']:
            raise CloudifyCliError('{0} is already the current active node!'
                                   .format(node_name))
        break
    else:
        raise CloudifyCliError("Can't set node {0} as the active, "
                               "it's not a member of the cluster"
                               .format(node_name))

    client.cluster.update(master=node_name)
    logger.info('{0} set as the new active node'.format(node_name))


@cluster.group(name='nodes')
def nodes():
    """Handle the cluster nodes [cluster only]
    """


@nodes.command(name='list',
               short_help='List the nodes in the cluster [cluster only]')
@pass_cluster_client()
@cfy.pass_logger
def list_nodes(client, logger):
    """Display a table with basic information about the nodes in the cluster
    """
    response = client.cluster.nodes.list()
    default = {'master': False, 'online': False}
    print_data(CLUSTER_COLUMNS, response, 'HA Cluster nodes', defaults=default)


@nodes.command(name='remove',
               short_help='Remove a node from the cluster [cluster only]')
@pass_cluster_client()
@cfy.pass_logger
@cfy.argument('cluster-node-name')
def remove_node(client, logger, cluster_node_name):
    """Unregister a node from the cluster.

    Note that this will not teardown the removed node, only remove it from
    the cluster. Removed replicas are not usable as Cloudify Managers,
    so it is left to the user to examine and teardown the node.
    """
    cluster_nodes = {node['name']: node.host_ip
                     for node in client.cluster.nodes.list()}

    if cluster_node_name not in cluster_nodes:
        raise CloudifyCliError('Invalid command. {0} is not a member of '
                               'the cluster.'.format(cluster_node_name))
    removed_ip = cluster_nodes[cluster_node_name]

    client.cluster.nodes.delete(cluster_node_name)

    env.profile.cluster = [node for node in env.profile.cluster
                           if node['manager_ip'] != removed_ip]
    env.profile.save()
    logger.info('Node {0} was removed successfully!'
                .format(cluster_node_name))


def _join_node_to_profile(from_profile, joined_profile=None):
    if joined_profile is None:
        joined_profile = from_profile
    node = {node_attr: getattr(from_profile, node_attr)
            for node_attr in env.CLUSTER_NODE_ATTRS}
    cert_file = env.get_ssl_cert()
    if cert_file:
        profile_cert = os.path.join(
            joined_profile.workdir,
            '{0}_{1}'.format(constants.PUBLIC_REST_CERT, node['manager_ip']))
        shutil.copy(cert_file, profile_cert)
    else:
        profile_cert = None

    if from_profile.ssh_key:
        ssh_key = os.path.join(
            joined_profile.workdir,
            'ssh_{0}'.format(node['manager_ip']))
        try:
            shutil.copy(from_profile.ssh_key, ssh_key)
        except IOError:
            # even if the key file doesn't exist, it's sometimes set in the
            # profile
            ssh_key = None
    else:
        ssh_key = None

    node.update({
        'cert': profile_cert,
        'trust_all': env.get_ssl_trust_all(),
        'ssh_key': ssh_key
    })
    joined_profile.cluster.append(node)
    joined_profile.save()


def _copy_cluster_profile_settings(from_profile, to_profile):
    """After joining to the cluster, make local profile also use it.

    Copy the nodes and the certs + ssh keys of the cluster, from the
    joined-to profile.
    """
    for attr in ['manager_username', 'manager_password', 'manager_tenant']:
        setattr(to_profile, attr, getattr(from_profile, attr))

    for node in from_profile.cluster:
        added_node = node.copy()
        for file_key in ['cert', 'ssh_key']:
            path = node.get(file_key)
            if not path:
                continue
            filename = os.path.basename(path)
            new_filename = os.path.join(to_profile.workdir, filename)
            # use .copy2 to also preserve chmod
            shutil.copy2(node[file_key], new_filename)
            added_node[file_key] = new_filename
        to_profile.cluster.append(added_node)
    to_profile.save()


def _display_logs(logger, logs):
    for log in logs:
        timestamp = datetime.utcfromtimestamp(log['timestamp'] // 1e6)
        logger.info(u'{0} {1}'.format(timestamp.isoformat(),
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
            logger.debug('Error while fetching cluster status: {0}'
                         .format(e))
        else:
            if logger and status.logs:
                last_log = status.logs[-1]['cursor']
                _display_logs(logger, status.logs)

            if status.initialized or status.error:
                return status

        time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)
