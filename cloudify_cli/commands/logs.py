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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os

import click

from .. import ssh
from .. import utils
from ..config import options
from ..config import helptexts
from ..logger import get_logger


@click.group(name='logs', context_settings=utils.CLICK_CONTEXT_SETTINGS)
def logs():
    """Handle manager service logs
    """
    pass


def _archive_logs():
    """Creates an archive of all logs found under /var/log/cloudify plus
    journalctl.
    """
    logger = get_logger()
    archive_filename = 'cloudify-manager-logs_{0}_{1}.tar.gz'.format(
        ssh.get_manager_date(), utils.get_management_server_ip())
    archive_path = os.path.join('/tmp', archive_filename)
    journalctl_destination_path = '/var/log/cloudify/journalctl.log'

    ssh.run_command_on_manager(
        'journalctl > /tmp/jctl && '
        'mv /tmp/jctl {0}'.format(journalctl_destination_path), use_sudo=True)
    logger.info('Creating logs archive in manager: {0}'.format(archive_path))
    # We skip checking if the tar executable can be found on the machine
    # knowingly. We don't want to run another ssh command just to verify
    # something that will almost never happen.
    ssh.run_command_on_manager('tar -czf {0} -C /var/log cloudify'.format(
        archive_path), use_sudo=True)
    ssh.run_command_on_manager(
        'rm {0}'.format(journalctl_destination_path), use_sudo=True)
    return archive_path


@logs.command(name='download')
@options.output_path
def download(output_path):
    """Download an archive containing all of the manager's service logs
    """
    logger = get_logger()
    archive_path_on_manager = _archive_logs()
    logger.info('Downloading archive to: {0}'.format(output_path))
    ssh.get_file_from_manager(archive_path_on_manager, output_path)
    logger.info('Removing archive from manager...')
    ssh.run_command_on_manager(
        'rm {0}'.format(archive_path_on_manager), use_sudo=True)


@logs.command(name='purge')
@options.force(help=helptexts.FORCE_PURGE_LOGS)
@click.option('--backup-first',
              is_flag=True,
              help=helptexts.BACKUP_LOGS_FIRST)
def purge(force, backup_first):
    """Truncate all logs files under /var/log/cloudify.

    This allows the user to take extreme measures to clean up data from the
    manager. For instance, when the disk is full due to some bug causing the
    logs to bloat up.

    The `-f, --force` flag is mandatory as a safety measure.
    """
    logger = get_logger()
    if backup_first:
        backup()

    logger.info('Purging manager logs...')
    # well, we could've just `find /var/log/cloudify -name "*" -type f -delete`
    # thing is, it will delete all files and nothing will be written into them
    # until the relevant service is restarted.
    ssh.run_command_on_manager(
        'for f in $(sudo find /var/log/cloudify -name "*" -type f); '
        'do sudo truncate -s 0 $f; '
        'done', use_sudo=True)


@logs.command(name='backup')
def backup():
    """Create a backup of all logs under a single archive and save it
    on the manager under /var/log.
    """
    logger = get_logger()
    archive_path_on_manager = _archive_logs()
    logger.info('Backing up manager logs to /var/log/{0}'.format(
        os.path.basename(archive_path_on_manager)))
    ssh.run_command_on_manager('mv {0} {1}'.format(
        archive_path_on_manager, '/var/log/'), use_sudo=True)
