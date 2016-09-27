########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

from .. import table
from .. import utils
from ..cli import helptexts, cfy


@cfy.group(name='snapshots')
@cfy.options.verbose()
@cfy.assert_manager_active()
def snapshots():
    """Handle manager snapshots
    """
    pass


@snapshots.command(name='restore',
                   short_help='Restore a manager from a snapshot '
                   '[manager only]')
@cfy.argument('snapshot-id')
@cfy.options.without_deployment_envs
@cfy.options.force(help=helptexts.FORCE_RESTORE_ON_DIRTY_MANAGER)
@cfy.options.verbose()
@cfy.pass_client()
@cfy.pass_logger
def restore(snapshot_id, without_deployment_envs, force, logger, client):
    """Restore a manager to its previous state

    `SNAPSHOT_ID` is the id of the snapshot to use for restoration.
    """
    logger.info('Restoring snapshot {0}...'.format(snapshot_id))
    execution = client.snapshots.restore(
        snapshot_id, not without_deployment_envs, force)
    logger.info("Started workflow execution. The execution's id is {0}".format(
        execution.id))


@snapshots.command(name='create',
                   short_help='Create a snapshot [manager only]')
@cfy.argument('snapshot-id', required=False)
@cfy.options.include_metrics
@cfy.options.exclude_credentials
@cfy.options.verbose()
@cfy.pass_client()
@cfy.pass_logger
def create(snapshot_id, include_metrics, exclude_credentials, logger, client):
    """Create a snapshot on the manager

    The snapshot will contain the relevant data to restore a manager to
    its previous state.

    `SNAPSHOT_ID` is the id to attach to the snapshot.
    """
    snapshot_id = snapshot_id or utils.generate_suffixed_id('snapshot')
    logger.info('Creating snapshot {0}...'.format(snapshot_id))

    execution = client.snapshots.create(snapshot_id,
                                        include_metrics,
                                        not exclude_credentials)
    logger.info("Started workflow execution. The execution's id is {0}".format(
        execution.id))


@snapshots.command(name='delete',
                   short_help='Delete a snapshot [manager only]')
@cfy.argument('snapshot-id')
@cfy.options.verbose()
@cfy.pass_client()
@cfy.pass_logger
def delete(snapshot_id, logger, client):
    """Delete a snapshot from the manager

    `SNAPSHOT_ID` is the id of the snapshot to download.
    """
    logger.info('Deleting snapshot {0}...'.format(snapshot_id))
    client.snapshots.delete(snapshot_id)
    logger.info('Snapshot deleted successfully')


@snapshots.command(name='upload',
                   short_help='Upload a snapshot [manager only]')
@cfy.argument('snapshot_path')
@cfy.options.snapshot_id
@cfy.options.verbose()
@cfy.pass_client()
@cfy.pass_logger
def upload(snapshot_path, snapshot_id, logger, client):
    """Upload a snapshot to the manager

    `SNAPSHOT_PATH` is the path to the snapshot to upload.
    """
    snapshot_id = snapshot_id or utils.generate_suffixed_id('snapshot')

    logger.info('Uploading snapshot {0}...'.format(snapshot_path))
    progress_handler = utils.generate_progress_handler(snapshot_path, '')
    snapshot = client.snapshots.upload(snapshot_path,
                                       snapshot_id,
                                       progress_handler)
    logger.info("Snapshot uploaded. The snapshot's id is {0}".format(
        snapshot.id))


@snapshots.command(name='download',
                   short_help='Download a snapshot [manager only]')
@cfy.argument('snapshot-id')
@cfy.options.output_path
@cfy.options.verbose()
@cfy.pass_client()
@cfy.pass_logger
def download(snapshot_id, output_path, logger, client):
    """Download a snapshot from the manager

    `SNAPSHOT_ID` is the id of the snapshot to download.
    """
    logger.info('Downloading snapshot {0}...'.format(snapshot_id))
    snapshot_name = output_path if output_path else snapshot_id
    progress_handler = utils.generate_progress_handler(snapshot_name, '')
    target_file = client.snapshots.download(snapshot_id,
                                            output_path,
                                            progress_handler)
    logger.info('Snapshot downloaded as {0}'.format(target_file))


@snapshots.command(name='list',
                   short_help='List snapshots [manager only]')
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.verbose()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by, descending, logger, client):
    """List all snapshots on the manager
    """
    logger.info('Listing snapshots...')
    snapshots = client.snapshots.list(sort=sort_by, is_descending=descending)

    columns = ['id', 'created_at', 'status', 'error']
    pt = table.generate(columns, data=snapshots)
    table.log('Snapshots:', pt)
