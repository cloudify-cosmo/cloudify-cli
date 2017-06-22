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

import time

from ..table import print_data
from .. import utils
from ..cli import helptexts, cfy
from ..exceptions import SuppressedCloudifyCliError
from cloudify_rest_client.executions import Execution

SNAPSHOT_COLUMNS = ['id', 'created_at', 'status', 'error', 'permission',
                    'tenant_name', 'created_by']


@cfy.group(name='snapshots')
@cfy.options.verbose()
@cfy.assert_manager_active()
def snapshots():
    """Handle manager snapshots
    """
    pass


@cfy.pass_logger
def _wait_for_restore_worfklows(execution, client, logger,
                                attempts=600, retry_delay=3):
    """
        Wait for a restore-related workflow to end for up to 30 minutes.
        In cases of unresolvable from source plugin installs the manager
        has been observed to take 25+ minutes. If the restore takes
        longer than this then it is likely to fail.

        We do not use the pass_client decorator because we need to respect the
        modified client that is passed to us for the deployment environment
        recreation.
    """
    execution_ended = False
    attempt = 0
    while attempt < attempts:
        if not execution_ended:
            execution = client.executions.get(execution['id'])
            execution_ended = execution.status in Execution.END_STATES

        if execution_ended:
            break

        if attempt > 0 and attempt % 10 == 0:
            logger.info('Waiting...')

        time.sleep(retry_delay)
        attempt += 1

    if execution_ended:
        return execution
    else:
        logger.error('Execution did not complete in time.')
        raise SuppressedCloudifyCliError()


@snapshots.command(name='restore',
                   short_help='Restore a manager from a snapshot '
                   '[manager only]')
@cfy.argument('snapshot-id')
@cfy.options.without_deployment_envs
@cfy.options.force(help=helptexts.FORCE_RESTORE_ON_DIRTY_MANAGER)
@cfy.options.tenant_name(required=False,
                         help=helptexts.RESTORE_SNAPSHOT_TENANT_NAME,
                         show_default_in_help=False)
@cfy.options.restore_certificates
@cfy.options.no_reboot
@cfy.options.verbose()
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def restore(snapshot_id,
            without_deployment_envs,
            force,
            tenant_name,
            restore_certificates,
            no_reboot,
            logger,
            client):
    """Restore a manager to its previous state

    `SNAPSHOT_ID` is the id of the snapshot to use for restoration.
    """
    logger.info('Restoring snapshot {0}...'.format(snapshot_id))
    recreate_deployments_envs = not without_deployment_envs
    execution = client.snapshots.restore(
        snapshot_id,
        recreate_deployments_envs,
        force,
        tenant_name,
        restore_certificates,
        no_reboot
    )

    if recreate_deployments_envs:
        # This is intended as a temporary measure so the interface has not
        # been modified in an effort to avoid introducing an option for only
        # this version and then either deprecating or removing it on the next
        # version which would then require a major version increase due to
        # breaking compatibility.
        logger.info(
            'Deployment environments will be recreated after snapshot '
            'restore workflow completes. Waiting up to 30 minutes...'
        )
        execution = _wait_for_restore_worfklows(execution, client)

        if execution.error:
            logger.error('Snapshot restore failed with error: {error}'.format(
                error=execution.error))
            raise SuppressedCloudifyCliError()
        else:
            logger.info('Snapshot restore workflow completed.')
            failures = False
            tenants = [tenant['name'] for tenant in client.tenants.list()]
            logger.info(
                'Restoring deployment environments for: {tenants}'.format(
                    tenants=','.join(tenants),
                )
            )
            for tenant in tenants:
                logger.info(
                    'Restoring deployment environments for {tenant}'.format(
                        tenant=tenant,
                    )
                )
                client._client.headers['Tenant'] = tenant
                execution = (
                    client.snapshots._restore_deployment_environments()
                )
                # Using same timeout and other settings due to same
                # expectations of failure timing
                execution = _wait_for_restore_worfklows(execution, client)
                if execution.error:
                    failures = True
                    logger.warn(
                        'Failed to restore deployment environments for '
                        '{tenant}, with error: {error}'.format(
                            tenant=tenant,
                            error=execution.error,
                        )
                    )
                else:
                    logger.info(
                        'Successfully restored deployment environments for '
                        '{tenant}'.format(
                            tenant=tenant,
                        )
                    )

            if failures:
                raise SuppressedCloudifyCliError()
    else:
        logger.info(
            "Started workflow execution. The execution's id is {0}".format(
                execution['id'],
            )
        )

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
@cfy.argument('snapshot-id', required=False)
@cfy.options.include_metrics
@cfy.options.exclude_credentials
@cfy.options.private_resource
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='snapshot')
@cfy.pass_client()
@cfy.pass_logger
def create(snapshot_id,
           include_metrics,
           exclude_credentials,
           private_resource,
           logger,
           client,
           tenant_name):
    """Create a snapshot on the manager

    The snapshot will contain the relevant data to restore a manager to
    its previous state.

    `SNAPSHOT_ID` is the id to attach to the snapshot.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    snapshot_id = snapshot_id or utils.generate_suffixed_id('snapshot')
    logger.info('Creating snapshot {0}...'.format(snapshot_id))

    execution = client.snapshots.create(snapshot_id,
                                        include_metrics,
                                        not exclude_credentials,
                                        private_resource)
    logger.info("Started workflow execution. The execution's id is {0}".format(
        execution.id))


@snapshots.command(name='delete',
                   short_help='Delete a snapshot [manager only]')
@cfy.argument('snapshot-id')
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='snapshot')
@cfy.pass_client()
@cfy.pass_logger
def delete(snapshot_id, logger, client, tenant_name):
    """Delete a snapshot from the manager

    `SNAPSHOT_ID` is the id of the snapshot to download.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Deleting snapshot {0}...'.format(snapshot_id))
    client.snapshots.delete(snapshot_id)
    logger.info('Snapshot deleted successfully')


@snapshots.command(name='upload',
                   short_help='Upload a snapshot [manager only]')
@cfy.argument('snapshot_path')
@cfy.options.snapshot_id
@cfy.options.private_resource
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='snapshot')
@cfy.pass_client()
@cfy.pass_logger
def upload(snapshot_path,
           snapshot_id,
           private_resource,
           logger,
           client,
           tenant_name):
    """Upload a snapshot to the manager

    `SNAPSHOT_PATH` is the path to the snapshot to upload.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    snapshot_id = snapshot_id or utils.generate_suffixed_id('snapshot')

    logger.info('Uploading snapshot {0}...'.format(snapshot_path))
    progress_handler = utils.generate_progress_handler(snapshot_path, '')
    snapshot = client.snapshots.upload(snapshot_path,
                                       snapshot_id,
                                       private_resource,
                                       progress_handler)
    logger.info("Snapshot uploaded. The snapshot's id is {0}".format(
        snapshot.id))


@snapshots.command(name='download',
                   short_help='Download a snapshot [manager only]')
@cfy.argument('snapshot-id')
@cfy.options.output_path
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='snapshot')
@cfy.pass_client()
@cfy.pass_logger
def download(snapshot_id, output_path, logger, client, tenant_name):
    """Download a snapshot from the manager

    `SNAPSHOT_ID` is the id of the snapshot to download.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
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
@cfy.options.verbose()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by, descending, tenant_name, all_tenants, logger, client):
    """List all snapshots on the manager
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Listing snapshots...')
    snapshots = client.snapshots.list(sort=sort_by,
                                      is_descending=descending,
                                      _all_tenants=all_tenants)

    print_data(SNAPSHOT_COLUMNS, snapshots, 'Snapshots:')
