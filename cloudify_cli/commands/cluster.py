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
import yaml
import shutil
from functools import wraps
from datetime import datetime
from requests.exceptions import ReadTimeout, ConnectionError

from cloudify_rest_client.exceptions import (CloudifyClientError,
                                             NotClusterMaster)

from .. import constants, env
from ..cli import cfy
from ..table import print_data
from ..exceptions import CloudifyCliError
from ..execution_events_fetcher import WAIT_FOR_EXECUTION_SLEEP_INTERVAL


CLUSTER_COLUMNS = ['name', 'host_ip', 'state', 'consul',
                   'services', 'database', 'heartbeat']
CLUSTER_COLUMNS_DEFAULTS = {'state': 'offline', 'consul': 'FAIL',
                            'services': 'FAIL', 'database': 'FAIL',
                            'heartbeat': 'FAIL'}


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
@cfy.options.verbose()
def status(client, logger):
    """Display the current status of the Cloudify Manager cluster
    """
    status = client.cluster.status()
    if status.initialized:
        logger.info('Cloudify Manager cluster ready\n')
    else:
        logger.info('Cloudify Manager cluster not initialized\n')


@cluster.command(name='start',
                 short_help='Start a Cloudify Manager cluster [manager only]')
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.verbose()
@cfy.options.timeout()
@cfy.options.cluster_node_options
@cfy.options.cluster_host_ip
@cfy.options.cluster_node_name
def start(client,
          logger,
          timeout,
          options,
          cluster_host_ip,
          cluster_node_name):
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
        options=options
    )
    status = _wait_for_cluster_initialized(client, logger, timeout=timeout)

    if status.error:
        logger.error('Error while configuring the Cloudify Manager cluster')
        raise CloudifyCliError(status.error)

    env.profile.profile_name = env.profile.manager_ip
    _join_node_to_profile(cluster_node_name, env.profile)

    logger.info('Cloudify Manager cluster started at {0}.\n'
                .format(cluster_host_ip))


@cluster.command(name='join',
                 short_help='Join a Cloudify Manager cluster [manager only]')
@cfy.pass_client()
@cfy.pass_logger
@cfy.argument('join_profile')
@cfy.options.verbose()
@cfy.options.timeout()
@cfy.options.cluster_node_options
@cfy.options.cluster_host_ip
@cfy.options.cluster_node_name
def join(client,
         logger,
         join_profile,
         timeout,
         options,
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
    cluster_nodes = cluster_client.cluster.nodes.list()
    if any(n.name == cluster_node_name for n in cluster_nodes):
        raise CloudifyCliError('Node {0} is already a member of the cluster'
                               .format(cluster_node_name))
    join = [n.host_ip for n in cluster_nodes]
    logger.info('Joining the Cloudify Manager cluster: {0}'
                .format(join))
    new_cluster_node = cluster_client.cluster.nodes.add(
        host_ip=cluster_host_ip,
        node_name=cluster_node_name)

    client.cluster.join(
        host_ip=cluster_host_ip,
        node_name=cluster_node_name,
        credentials=new_cluster_node.credentials,
        required=new_cluster_node.required,
        join_addrs=join,
        options=options
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

    _join_node_to_profile(cluster_node_name, env.profile,
                          joined_profile=joined_profile)
    _copy_cluster_profile_settings(from_profile=joined_profile,
                                   to_profile=env.profile)
    logger.info('Cloudify Manager joined cluster successfully.')


@cluster.command(name='update-profile',
                 short_help='Store the cluster nodes in the CLI profile '
                            '[cluster only]')
@pass_cluster_client()
@cfy.pass_logger
@cfy.options.verbose()
def update_profile(client, logger):
    """Fetch the list of the cluster nodes and update the current profile.

    Use this to update the profile if nodes are added to the cluster from
    another machine. Only the cluster nodes that are stored in the profile
    will be contacted in case of a cluster master failure.
    """
    logger.info('Fetching the cluster nodes list...')
    nodes = client.cluster.nodes.list()
    _update_profile_cluster_settings(env.profile, nodes, logger=logger)
    logger.info('Profile is up to date with {0} nodes'
                .format(len(env.profile.cluster)))


def _update_profile_cluster_settings(profile, nodes, logger=None):
    """Update the cluster list set in profile with the received nodes

    We will merge the received nodes into the stored list - adding and
    removing when necessary - and not just set the profile list to the
    received nodes, because the profile might have more details about
    the nodes (eg. a certificate path)
    """
    stored_nodes = {node.get('name') for node in env.profile.cluster}
    received_nodes = {node.name for node in nodes}
    if env.profile.cluster is None:
        env.profile.cluster = []
    for node in nodes:
        if node.name not in stored_nodes:
            if logger:
                logger.info('Adding cluster node {0} to local profile'
                            .format(node.host_ip))
            env.profile.cluster.append({
                'name': node.name,
                # all other conenction parameters will be defaulted to the
                # ones from the last used manager
                'manager_ip': node.host_ip
            })
    # filter out removed nodes
    env.profile.cluster = [n for n in env.profile.cluster
                           if n['name'] in received_nodes]
    env.profile.save()


@cluster.command(name='set-active',
                 short_help='Set one of the cluster nodes as the new active '
                            '[cluster only]')
@cfy.argument('node_name')
@cfy.options.verbose()
@cfy.options.timeout(default=60)
@pass_cluster_client()
@cfy.pass_logger
def set_active(client, logger, node_name, timeout, poll_interval=1):
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

    deadline = time.time() + timeout
    try:
        client.cluster.update(master=node_name)
    except ReadTimeout:
        pass
    logger.info('Waiting for {0} to become the active node...'
                .format(node_name))
    while time.time() < deadline:
        try:
            nodes = client.cluster.nodes.list()
        except CloudifyClientError:
            time.sleep(poll_interval)
            continue

        if any(node['name'] == node_name and node['master'] for node in nodes):
            logger.info('{0} set as the new active node'.format(node_name))
            break
        time.sleep(poll_interval)
    else:
        logger.error('Timed out while waiting for {0} to be set as the '
                     'new active node'.format(node_name))


@cluster.group(name='nodes')
def nodes():
    """Handle the cluster nodes [cluster only]
    """


def _prepare_node(node):
    """Normalize node for display in a table"""
    checks = node.pop('checks', {})
    checks = {check: 'OK' if passing else 'FAIL'
              for check, passing in checks.items()}
    node.update(checks)
    online = node.pop('online', False)
    master = node.pop('master', False)
    if online:
        node['state'] = 'leader' if master else 'replica'
    else:
        node['state'] = 'offline'


@nodes.command(name='list',
               short_help='List the nodes in the cluster [cluster only]')
@pass_cluster_client()
@cfy.pass_logger
@cfy.options.verbose()
def list_nodes(client, logger):
    """Display a table with basic information about the nodes in the cluster
    """
    response = client.cluster.nodes.list()
    for node in response:
        _prepare_node(node)
    print_data(CLUSTER_COLUMNS, response, 'HA Cluster nodes',
               defaults=CLUSTER_COLUMNS_DEFAULTS,
               labels={'services': 'cloudify services'})
    _update_profile_cluster_settings(env.profile, response, logger=logger)


@nodes.command(name='get',
               short_help='Show cluster node details [cluster only]')
@pass_cluster_client()
@cfy.pass_logger
@cfy.argument('cluster-node-name')
@cfy.options.verbose()
def get_node(client, logger, cluster_node_name):
    node = client.cluster.nodes.details(cluster_node_name)
    _prepare_node(node)
    print_data(CLUSTER_COLUMNS, [node], 'Node {0}'.format(cluster_node_name),
               defaults=CLUSTER_COLUMNS_DEFAULTS,
               labels={'services': 'cloudify services'})
    options = node.get('options')
    if options:
        logger.info('Node configuration:')
        logger.info(yaml.safe_dump(options, default_flow_style=False))


@nodes.command(name='update',
               short_help='Update the options for a cluster node '
                          '[cluster only]')
@pass_cluster_client()
@cfy.pass_logger
@cfy.options.cluster_node_options
@cfy.argument('cluster-node-name')
@cfy.options.verbose()
def update_node_options(client, logger, cluster_node_name,
                        cluster_node_options):
    if not cluster_node_options:
        raise CloudifyCliError('Need an inputs file to update node options')
    client.cluster.nodes.update(cluster_node_name, cluster_node_options)
    logger.info('Node {0} updated'.format(cluster_node_name))


@nodes.command(name='set-certificate')
@cfy.pass_logger
@cfy.argument('cluster-node-name')
@cfy.argument('certificate-path')
def set_node_certificate(logger, cluster_node_name, certificate_path):
    """Set REST certificate for the given cluster node."""
    certificate_path = os.path.expanduser(certificate_path)
    if not os.path.exists(certificate_path):
        raise CloudifyCliError('Certificate file {0} does not exist'
                               .format(certificate_path))

    for node in env.profile.cluster:
        if node['name'] == cluster_node_name:
            node['cert'] = certificate_path
            break
    else:
        raise CloudifyCliError('Node {0} not found in the cluster profile'
                               .format(cluster_node_name))
    env.profile.save()


@nodes.command(name='remove',
               short_help='Remove a node from the cluster [cluster only]')
@pass_cluster_client()
@cfy.pass_logger
@cfy.argument('cluster-node-name')
@cfy.options.verbose()
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
    removed_node_ip = cluster_nodes[cluster_node_name]

    client.cluster.nodes.delete(cluster_node_name)

    for profile_name in env.get_profile_names():
        profile_context = env.get_profile_context(profile_name)

        if profile_context.profile_name == removed_node_ip:
            logger.info('Profile {0} set as a non-cluster profile'
                        .format(profile_context.profile_name))
            profile_context.cluster = []
            if hasattr(profile_context, '_original'):
                for attrname, attr in profile_context._original.items():
                    setattr(profile_context, attrname, attr)
        else:
            logger.info(
                'Profile {0}: {1} removed from cluster nodes list'
                .format(profile_context.profile_name, cluster_node_name))
            profile_context.cluster = [
                node for node in profile_context.cluster
                if node.get('name') != cluster_node_name]
        profile_context.save()

    logger.info('Node {0} was removed successfully!'
                .format(cluster_node_name))


def _join_node_to_profile(node_name, from_profile, joined_profile=None):
    if joined_profile is None:
        joined_profile = from_profile
    node = {node_attr: getattr(from_profile, node_attr)
            for node_attr in env.CLUSTER_NODE_ATTRS}
    cert_file = env.get_ssl_cert()

    from_profile._original = {attrname: getattr(from_profile, attrname)
                              for attrname in env.CLUSTER_NODE_ATTRS}
    from_profile.save()
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
        'name': node_name,
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
        except (ConnectionError, CloudifyClientError) as e:
            # during cluster initialization, we restart the database - while
            # that happens, the server might return intermittent 500 errors;
            # we also restart the restservice and nginx, which might lead
            # to intermittent connection errors
            logger.debug('Error while fetching cluster status: {0}'
                         .format(e))
        else:
            if logger and status.logs:
                last_log = status.logs[-1]['cursor']
                _display_logs(logger, status.logs)

            if status.initialized or status.error:
                return status

        time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)
