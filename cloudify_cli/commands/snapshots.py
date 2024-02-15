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

from cloudify.snapshots import STATES

from cloudify_cli import utils
from cloudify_cli.table import print_data
from cloudify_cli.cli import helptexts, cfy
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.execution_events_fetcher import wait_for_execution

SNAPSHOT_COLUMNS = ['id', 'created_at', 'status', 'error',
                    'visibility', 'tenant_name', 'created_by']

SNAPSHOT_STATUSES = {
    STATES.RUNNING: 'Snapshot restore in progress... This may take a while, '
                    'depending on the snapshot size',
    STATES.NOT_RUNNING: 'No snapshot is currently being restored'
}


@cfy.group(name='snapshots')
@cfy.options.common_options
@cfy.assert_manager_active()
def snapshots():
    """Handle manager snapshots
    """


@snapshots.command(name='restore',
                   short_help='Restore a manager from a snapshot '
                   '[manager only]')
@cfy.argument('snapshot-id')
@cfy.options.force(help=helptexts.FORCE_RESTORE_ON_DIRTY_MANAGER)
@cfy.options.restore_certificates
@cfy.options.no_reboot
@cfy.options.ignore_plugin_failure
@cfy.options.common_options
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def restore(snapshot_id,
            force,
            restore_certificates,
            no_reboot,
            ignore_plugin_failure,
            logger,
            client):
    """Restore a manager to its previous state

    `SNAPSHOT_ID` is the id of the snapshot to use for restoration.
    """
    logger.info('Restoring snapshot {0}...'.format(snapshot_id))
    execution = client.snapshots.restore(
        snapshot_id,
        force,
        restore_certificates,
        no_reboot,
        ignore_plugin_failure
    )
    logger.info("Started workflow execution. The execution's id is {0}. "
                "You can use `cfy snapshots status` to check for the "
                "restore status.".format(execution.id))

    if not restore_certificates:
        return
    if no_reboot:
        logger.warn('Certificates might be replaced during a snapshot '
                    'restore action. It is recommended that you reboot the '
                    'Manager VM when the execution is terminated, or several '
                    'services might not work.')
    else:
        logger.info('In the event of a certificates restore action, the '
                    'Manager VM will automatically reboot after execution is '
                    'terminated. After reboot the Manager can work with the '
                    'restored certificates.')


@snapshots.command(name='create',
                   short_help='Create a snapshot [manager only]')
@cfy.argument('snapshot-id', required=False, callback=cfy.validate_name)
@cfy.options.exclude_credentials
@cfy.options.exclude_logs
@cfy.options.exclude_events
@cfy.options.common_options
@cfy.options.queue_snapshot
@cfy.options.tempdir_path
@cfy.options.legacy
@cfy.options.listener_timeout
@cfy.options.wait_for_status
@cfy.pass_client()
@cfy.pass_logger
def create(snapshot_id,
           exclude_credentials,
           exclude_logs,
           exclude_events,
           queue,
           tempdir_path,
           legacy,
           listener_timeout,
           wait_for_status,
           logger,
           client):
    """Create a snapshot on the manager

    The snapshot will contain the relevant data to restore a manager to
    its previous state.

    `SNAPSHOT_ID` is the id to attach to the snapshot.
    """
    if legacy and listener_timeout:
        raise CloudifyCliError(
            'Listener timeout can be set only for non-legacy snapshots.')

    snapshot_id = snapshot_id or utils.generate_suffixed_id('snapshot')
    logger.info('Creating snapshot {0}...'.format(snapshot_id))

    execution = client.snapshots.create(snapshot_id,
                                        not exclude_credentials,
                                        not exclude_logs,
                                        not exclude_events,
                                        queue,
                                        tempdir_path=tempdir_path,
                                        legacy=legacy,
                                        listener_timeout=listener_timeout)
    started_log_msg = "Started workflow execution. The execution's id is" \
                      " {0}.".format(execution.id)
    queued_log_msg = '`queue` flag was passed, snapshot creation will start' \
                     ' automatically when possible. Execution id:' \
                     ' {0}'.format(execution.id)
    queued = True if execution.status == 'queued' else False
    logger.info(queued_log_msg) if queued else logger.info(started_log_msg)
    if wait_for_status:
        execution = wait_for_execution(
            client,
            client.executions.get(execution.id),
            timeout=None
        )
        if execution.error:
            logger.info("Snapshot %s creation failed [error=%s]",
                        snapshot_id, execution.error)
        else:
            logger.info('Successfully created snapshot %s.', snapshot_id)


@snapshots.command(name='delete',
                   short_help='Delete a snapshot [manager only]')
@cfy.argument('snapshot-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='snapshot')
@cfy.pass_client()
@cfy.pass_logger
def delete(snapshot_id, logger, client, tenant_name):
    """Delete a snapshot from the manager

    `SNAPSHOT_ID` is the id of the snapshot to download.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Deleting snapshot {0}...'.format(snapshot_id))
    client.snapshots.delete(snapshot_id)
    logger.info('Snapshot deleted successfully')


@snapshots.command(name='upload',
                   short_help='Upload a snapshot [manager only]')
@cfy.argument('snapshot_path')
@cfy.options.snapshot_id(validate=True)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='snapshot')
@cfy.pass_client()
@cfy.pass_logger
def upload(snapshot_path,
           snapshot_id,
           logger,
           client,
           tenant_name):
    """Upload a snapshot to the manager

    `SNAPSHOT_PATH` is the path to the snapshot to upload.
    """
    if client.manager.get_version().get('edition') == 'premium':
        client.license.check()
    utils.explicit_tenant_name_message(tenant_name, logger)
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
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='snapshot')
@cfy.pass_client()
@cfy.pass_logger
def download(snapshot_id, output_path, logger, client, tenant_name):
    """Download a snapshot from the manager

    `SNAPSHOT_ID` is the id of the snapshot to download.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
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
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='snapshot')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def list(sort_by,
         descending,
         tenant_name,
         all_tenants,
         search,
         pagination_offset,
         pagination_size,
         logger,
         client):
    """List all snapshots on the manager
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing snapshots...')
    snapshots = client.snapshots.list(sort=sort_by,
                                      is_descending=descending,
                                      _all_tenants=all_tenants,
                                      _search=search,
                                      _offset=pagination_offset,
                                      _size=pagination_size)

    print_data(SNAPSHOT_COLUMNS, snapshots, 'Snapshots:')
    total = snapshots.metadata.pagination.total
    logger.info('Showing {0} of {1} snapshots'.format(len(snapshots), total))


@snapshots.command(name='status',
                   short_help='Show the status of the snapshot restore '
                              'workflow [manager only]')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def status(logger, client):
    """
    Return the status of the `restore_snapshot` workflow.
    """
    logger.info('Retrieving snapshot restore status...')
    status = client.snapshots.get_status()
    try:
        logger.info(SNAPSHOT_STATUSES[status['status']])
    except KeyError:
        logger.error("Unrecognized status received: %s", status)
