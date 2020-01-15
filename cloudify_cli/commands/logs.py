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

import os

from cloudify.cluster_status import CloudifyNodeType

from .. import ssh
from .. import env
from ..cli import helptexts, cfy
from ..exceptions import CloudifyCliError


@cfy.group(name='logs')
@cfy.options.common_options
@cfy.assert_manager_active()
def logs():
    """Handle manager service logs
    """
    pass


def _archive_logs(logger,
                  host_string,
                  node_type,
                  key_filename=None):
    """Creates an archive of all logs found under /var/log/cloudify plus
    journalctl.
    """
    archive_filename = 'cloudify-{node_type}-logs_{date}_{ip}.tar.gz'.format(
        node_type=node_type,
        date=ssh.get_host_date(host_string),
        ip=(env.profile.manager_ip if not host_string
            else host_string.split('@')[1]))
    archive_path = os.path.join('/tmp', archive_filename)
    journalctl_destination_path = '/var/log/cloudify/journalctl.log'

    ssh.run_command_on_host(
        'journalctl > /tmp/jctl && '
        'mv /tmp/jctl {0}'.format(journalctl_destination_path), use_sudo=True,
        host_string=host_string, key_filename=key_filename)
    logger.info('Creating logs archive in manager: {0}'.format(archive_path))
    # We skip checking if the tar executable can be found on the machine
    # knowingly. We don't want to run another ssh command just to verify
    # something that will almost never happen.
    ssh.run_command_on_host(
        'tar -czf {0} -C /var/log cloudify '
        '-C /opt/manager cluster_statuses '
        '--warning=no-file-changed'.format(archive_path),
        use_sudo=True,
        host_string=host_string,
        key_filename=key_filename,
        ignore_failure=True)
    ssh.run_command_on_host('test -e {0}'.format(archive_path),
                            host_string=host_string)
    ssh.run_command_on_host(
        'rm {0}'.format(journalctl_destination_path), use_sudo=True,
        host_string=host_string, key_filename=key_filename)
    return archive_path


@logs.command(name='download',
              short_help='Download manager service logs [manager only]')
@cfy.options.output_path
@cfy.options.all_nodes
@cfy.options.common_options
@cfy.pass_logger
def download(output_path, all_nodes, logger):
    """Download an archive containing all of the manager's service logs
    """
    if all_nodes:
        if not env.profile.cluster:
            raise CloudifyCliError(
                "No cluster nodes defined in this profile")
        cluster_nodes = _get_cluster_nodes()
        for node in cluster_nodes:
            ssh_user = node.get('ssh_user') or env.profile.ssh_user
            ssh_key = node.get('ssh_key') or env.profile.ssh_key
            if not ssh_user or not ssh_key:
                logger.info('No ssh details defined for host {0}, {1} in '
                            'cluster profile. Skipping...'
                            .format(node.get('hostname'), node.get('host_ip')))
                continue

            if not output_path:
                output_path = os.getcwd()
            host_string = env.build_host_string(ip=node.get('host_ip'),
                                                ssh_user=ssh_user)
            archive_path_on_host = _archive_logs(
                logger, host_string=host_string,
                node_type=node.get('host_type'), key_filename=ssh_key)
            logger.info('Downloading archive to: {0}'.format(output_path))
            ssh.get_file_from_host(archive_path_on_host,
                                   output_path,
                                   host_string=host_string,
                                   key_filename=ssh_key)
            logger.info('Removing archive from host...')
            ssh.run_command_on_host('rm {0}'.format(archive_path_on_host),
                                    use_sudo=True,
                                    host_string=host_string,
                                    key_filename=ssh_key)
    else:
        host_string = env.build_manager_host_string()
        archive_path_on_manager = _archive_logs(logger, host_string,
                                                CloudifyNodeType.MANAGER)
        if not output_path:
            output_path = os.getcwd()
        logger.info('Downloading archive to: {0}'.format(output_path))
        ssh.get_file_from_host(archive_path_on_manager,
                               output_path,
                               host_string)
        logger.info('Removing archive from manager...')
        ssh.run_command_on_host('rm {0}'.format(archive_path_on_manager),
                                host_string,
                                use_sudo=True)


def _get_cluster_nodes():
    cluster_nodes = []
    for nodes_list in env.profile.cluster.values():
        cluster_nodes.extend(nodes_list)
    return cluster_nodes


@logs.command(name='purge',
              short_help='Purge manager service logs [manager only]')
@cfy.options.force(help=helptexts.FORCE_PURGE_LOGS)
@cfy.options.backup_first
@cfy.options.common_options
@cfy.pass_logger
def purge(force, backup_first, logger):
    """Truncate all logs files under /var/log/cloudify.

    This allows the user to take extreme measures to clean up data from the
    manager. For instance, when the disk is full due to some bug causing the
    logs to bloat up.

    The `-f, --force` flag is mandatory as a safety measure.
    """
    if not force:
        raise CloudifyCliError(
            'You must supply the `-f, --force` flag to perform the purge')
    if backup_first:
        backup()

    host_string = env.build_manager_host_string()
    logger.info('Purging manager logs...')
    # well, we could've just `find /var/log/cloudify -name "*" -type f -delete`
    # thing is, it will delete all files and nothing will be written into them
    # until the relevant service is restarted.
    ssh.run_command_on_host(
        'for f in $(sudo find /var/log/cloudify -name "*" -type f); '
        'do sudo truncate -s 0 $f; '
        'done', host_string, use_sudo=True)


@logs.command(name='backup',
              short_help='Backup manager service logs [manager only]')
@cfy.options.common_options
@cfy.pass_logger
def backup(logger):
    """Create a backup of all logs under a single archive and save it
    on the manager under /var/log.
    """
    host_string = env.build_manager_host_string()
    archive_path_on_manager = _archive_logs(logger, host_string,
                                            CloudifyNodeType.MANAGER)
    logger.info('Backing up manager logs to /var/log/{0}'.format(
        os.path.basename(archive_path_on_manager)))
    ssh.run_command_on_host('mv {0} {1}'.format(
        archive_path_on_manager, '/var/log/'), host_string, use_sudo=True)
