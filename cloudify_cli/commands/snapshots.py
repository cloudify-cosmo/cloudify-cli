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

from .. import env
from .. import utils
from .. import common
from ..config import cfy
from ..config import helptexts
from ..logger import get_logger


@cfy.group(name='snapshots')
@cfy.options.verbose
def snapshots():
    """Handle manager snapshots
    """
    env.assert_manager_active()


@snapshots.command(name='restore')
@cfy.argument('snapshot-id')
@cfy.options.without_deployment_envs
@cfy.options.force(help=helptexts.FORCE_RESTORE_ON_DIRTY_MANAGER)
@cfy.options.verbose
def restore(snapshot_id, without_deployment_envs, force):
    """Restore a manager to its previous state

    `SNAPSHOT_ID` is the id of the snapshot to use for restoration.
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Restoring snapshot {0}...'.format(snapshot_id))
    execution = client.snapshots.restore(
        snapshot_id, not without_deployment_envs, force)
    logger.info("Started workflow execution. The execution's id is {0}".format(
        execution.id))


@snapshots.command(name='create')
@cfy.argument('snapshot-id', required=False)
@cfy.options.include_metrics
@cfy.options.exclude_credentials
@cfy.options.verbose
def create(snapshot_id, include_metrics, exclude_credentials):
    """Create a snapshot on the manager

    The snapshot will contain the relevant data to restore a manager to
    its previous state.

    `SNAPSHOT_ID` is the id to attach to the snapshot.
    """
    logger = get_logger()
    client = env.get_rest_client()

    snapshot_id = snapshot_id or utils.generate_suffixed_id('snapshot')
    logger.info('Creating snapshot {0}...'.format(snapshot_id))

    execution = client.snapshots.create(snapshot_id,
                                        include_metrics,
                                        not exclude_credentials)
    logger.info("Started workflow execution. The execution's id is {0}".format(
        execution.id))


@snapshots.command(name='delete')
@cfy.argument('snapshot-id')
@cfy.options.verbose
def delete(snapshot_id):
    """Delete a snapshot from the manager
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Deleting snapshot {0}...'.format(snapshot_id))
    client.snapshots.delete(snapshot_id)
    logger.info('Snapshot deleted successfully')


@snapshots.command(name='upload')
@cfy.argument('snapshot_path')
@cfy.options.snapshot_id
@cfy.options.verbose
def upload(snapshot_path, snapshot_id):
    """Upload a snapshot to the manager

    `SNAPSHOT_PATH` is the path to the snapshot to upload.
    """
    logger = get_logger()
    client = env.get_rest_client()

    snapshot_id = snapshot_id or utils.generate_suffixed_id('snapshot')

    logger.info('Uploading snapshot {0}...'.format(snapshot_path))
    progress_handler = utils.generate_progress_handler(snapshot_path, '')
    snapshot = client.snapshots.upload(snapshot_path,
                                       snapshot_id,
                                       progress_handler)
    logger.info("Snapshot uploaded. The snapshot's id is {0}".format(
        snapshot.id))


@snapshots.command(name='download')
@cfy.argument('snapshot-id')
@cfy.options.output_path
@cfy.options.verbose
def download(snapshot_id, output_path):
    """Download a snapshot from the manager

    `SNAPSHOT_ID` is the id of the snapshot to download.
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Downloading snapshot {0}...'.format(snapshot_id))
    snapshot_name = output_path if output_path else snapshot_id
    progress_handler = utils.generate_progress_handler(snapshot_name, '')
    target_file = client.snapshots.download(snapshot_id,
                                            output_path,
                                            progress_handler)
    logger.info('Snapshot downloaded as {0}'.format(target_file))


@snapshots.command(name='list')
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.verbose
def list(sort_by, descending):
    """List all snapshots on the manager
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Listing snapshots...')
    snapshots = client.snapshots.list(sort=sort_by, is_descending=descending)

    columns = ['id', 'created_at', 'status', 'error']
    pt = utils.table(columns, data=snapshots)
    common.print_table('Snapshots:', pt)
