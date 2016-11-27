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
                               'of a HA cluster')


@cfy.group(name='cluster')
@cfy.options.verbose()
def cluster():
    """Handle the Manager HA Cluster
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@cluster.command(name='status',
                 short_help='Show the current cluster status [cluster only]')
@cfy.pass_client()
@cfy.pass_logger
def status(client, logger):
    """Display the current status of the HA cluster
    """
    status = client.cluster.status()
    if not status.initialized:
        logger.error('This manager is not part of a Cloudify HA cluster')
    else:
        logger.info('HA cluster initialized!\nEncryption key: {0}'
                    .format(status.encryption_key))


@cluster.command(name='start',
                 short_help='Start a HA manager cluster [manager only]')
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.timeout()
@cfy.options.cluster_host_ip
@cfy.options.cluster_node_name
@cfy.options.cluster_encryption_key(with_default=True)
def start(client,
          logger,
          timeout,
          cluster_host_ip,
          cluster_node_name,
          cluster_encryption_key):
    """Start a HA manager cluster with the current manager as the master.

    This will initialize all the HA cluster components on the current manager,
    and mark it as the master. After that, other managers will be able to
    join the cluster by passing this manager's IP address and encryption key.
    """

    _verify_not_in_cluster(client)

    logger.info('Creating a new Cloudify HA cluster')

    client.cluster.start(config={
        'host_ip': cluster_host_ip,
        'node_name': cluster_node_name,
        'encryption_key': cluster_encryption_key
    })
    status = _wait_for_cluster_initialized(client, logger)

    if status.error:
        logger.error('Error while configuring the HA cluster')
        raise CloudifyCliError(status.error)

    logger.info('HA cluster started at {0}.\n'
                'Encryption key used is: {1}'
                .format(cluster_host_ip, cluster_encryption_key))


@cluster.command(name='join',
                 short_help='Join a HA manager cluster [manager only]')
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.timeout()
@cfy.options.cluster_host_ip
@cfy.options.cluster_node_name
@cfy.options.cluster_join
@cfy.options.cluster_encryption_key(with_default=True)
def join(client,
         logger,
         timeout,
         cluster_host_ip,
         cluster_node_name,
         cluster_encryption_key,
         cluster_join):
    """Join a HA cluster on this manager.

    A HA cluster with at least one machine needs to already exist.
    Pass the address of at least one member of the cluster as --cluster-join
    Specifying multiple addresses - even all members of the cluster - is
    encouraged, as it will allow to join the cluster even if some of the
    current members are unreachable, but is not required.
    """
    _verify_not_in_cluster(client)

    logger.info('Joining the Cloudify HA cluster: {0}'.format(cluster_join))

    client.cluster.join(config={
        'host_ip': cluster_host_ip,
        'node_name': cluster_node_name,
        'consul_key': cluster_encryption_key,
        'join_addrs': cluster_join
    })
    status = _wait_for_cluster_initialized(client, logger)

    if status.error:
        logger.error('Error while joining the HA cluster')
        raise CloudifyCliError(status.error)

    logger.info('HA cluster joined successfully!')


@cluster.group(name='nodes')
def nodes():
    pass


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

    while True:
        if timeout is not None:
            timeout -= WAIT_FOR_EXECUTION_SLEEP_INTERVAL
            if timeout < 0:
                raise CloudifyCliError('Timed out waiting for the HA '
                                       'cluster to be initialized.')

        status = client.cluster.status(
            _include=include,
            since=last_log)
        if status.logs:
            last_log = status.logs[-1]['cursor']

        for log in status.logs:
            timestamp = datetime.utcfromtimestamp(log['timestamp'] // 1e6)
            logger.info('{0} {1}'.format(timestamp.isoformat(),
                                         log['message']))

        if status.initialized or status.error:
            break
        time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)

    return status
