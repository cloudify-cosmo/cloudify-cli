########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import click

from cloudify_cli import utils
from cloudify_cli.config import helptexts
from cloudify_cli.logger import get_logger
from cloudify_cli.utils import print_table


@click.group(name='snapshots', context_settings=utils.CLICK_CONTEXT_SETTINGS)
def snapshots():
    """Handle manager snapshots
    """
    pass


@snapshots.command(name='restore')
@click.argument('snapshot-id', required=True)
@click.option('--without-deployments-envs',
              is_flag=True,
              help=helptexts.RESTORE_SNAPSHOT_EXCLUDE_EXISTING_DEPLOYMENTS)
@click.option('-f',
              '--force',
              is_flag=True,
              help=helptexts.FORCE_RESTORE_ON_DIRTY_MANAGER)
def restore(snapshot_id, without_deployments_envs, force):
    """Restore a manager to its previous state
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    ctx.logger.info('Restoring snapshot {0}...'.format(snapshot_id))
    client = utils.get_rest_client(management_ip)
    execution = client.snapshots.restore(
        snapshot_id, not without_deployments_envs, force)
    logger.info("Started workflow execution. The execution's id is {0}".format(
        execution.id))


@snapshots.command(name='create')
@click.argument('snapshot-id', required=False)
@click.option('--include-metrics',
              is_flag=True,
              help=helptexts.INCLUDE_METRICS_IN_SNAPSHOT)
@click.option('--exclude-credentials',
              is_flag=True,
              help=helptexts.EXCLUDE_CREDENTIALS_IN_SNAPSHOT)
def create(snapshot_id, include_metrics, exclude_credentials):
    """Create a snapshot on the manager

    The snapshot will contain the relevant data to restore a manager to
    its previous state.
    """
    logger = get_logger()
    snapshot_id = snapshot_id or utils._generate_suffixed_id('snapshot')
    management_ip = utils.get_management_server_ip()
    logger.info('Creating snapshot {0}...'.format(snapshot_id))
    client = utils.get_rest_client(management_ip)
    execution = client.snapshots.create(snapshot_id,
                                        include_metrics,
                                        not exclude_credentials)
    logger.info("Started workflow execution. The execution's id is {0}".format(
        execution.id))


@snapshots.command(name='delete')
@click.argument('snapshot-id', required=True)
def delete(snapshot_id):
    """Delete a snapshot from the manager
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info('Deleting snapshot {0}...'.format(snapshot_id))
    client = utils.get_rest_client(management_ip)
    client.snapshots.delete(snapshot_id)
    logger.info('Snapshot deleted successfully')


@snapshots.command(name='upload')
@click.argument('snapshot_path', required=True)
@click.option('-s',
              '--snapshot-id',
              required=False,
              help=helptexts.SNAPSHOT_ID)
def upload(snapshot_path, snapshot_id):
    """Upload a snapshot to the manager
    """
    logger = get_logger()
    snapshot_id = snapshot_id or utils._generate_suffixed_id('snapshot')
    management_ip = utils.get_management_server_ip()
    logger.info('Uploading snapshot {0}...'.format(snapshot_path))
    client = utils.get_rest_client(management_ip)
    snapshot = client.snapshots.upload(snapshot_path, snapshot_id)
    logger.info("Snapshot uploaded. The snapshot's id is {0}".format(
        snapshot.id))


@snapshots.command(name='download')
@click.argument('snapshot_id', required=True)
@click.option('-o',
              '--output-path',
              help=helptexts.OUTPUT_PATH)
def download(snapshot_id, output_path):
    """Download a snapshot from the manager
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info('Downloading snapshot {0}...'.format(snapshot_id))
    client = utils.get_rest_client(management_ip)
    target_file = client.snapshots.download(snapshot_id, output_path)
    logger.info('Snapshot downloaded as {0}'.format(target_file))


@snapshots.command(name='ls')
def ls():
    """List snapshots on the manager
    """
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)
    logger.info('Listing snapshots...')
    pt = utils.table(['id', 'created_at', 'status', 'error'],
                     data=client.snapshots.list())
    print_table('Snapshots:', pt)
