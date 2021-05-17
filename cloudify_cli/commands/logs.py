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
import json
import posixpath

from cloudify.cluster_status import CloudifyNodeType

from .. import env
from ..cli import helptexts, cfy
from ..exceptions import CloudifyCliError
from ..logger import (output,
                      CloudifyJSONEncoder,
                      get_global_json_output)


@cfy.group(name='logs')
@cfy.options.common_options
@cfy.assert_manager_active()
def logs():
    """Handle manager service logs
    """
    pass


def get_host_date(conn):
    return conn.run('date +%Y%m%dT%H%M%S', hide=True).stdout.strip()


def _archive_logs(conn, node_type, logger, node_ip):
    """Creates an archive of all logs found under /var/log/cloudify plus
    journalctl.
    """
    archive_filename = 'cloudify-{node_type}-logs_{date}_{ip}.tar.gz'.format(
        node_type=node_type,
        date=get_host_date(conn),
        ip=node_ip
    )
    archive_path = '/tmp/{}'.format(archive_filename)
    journalctl_destination_path = '/var/log/cloudify/journalctl.log'
    conn.sudo(
        'bash -c "journalctl > /tmp/jctl && mv /tmp/jctl {0}"'
        .format(journalctl_destination_path),
    )
    logger.info('Creating logs archive in {0}: {1}'.format(node_type,
                                                           archive_path))
    conn.sudo(
        'tar -czf {0} -C /var/log cloudify '
        '--warning=no-file-changed'.format(archive_path),
        warn=True
    )
    conn.run('test -e {0}'.format(archive_path))
    conn.sudo('rm {0}'.format(journalctl_destination_path))
    return archive_path


def _download_archive(conn, host_type, output_path,
                      logger, output_json, node_ip):
    archive_path_on_host = _archive_logs(conn, host_type, logger, node_ip)
    filename = posixpath.basename(archive_path_on_host)
    output_path = os.path.join(output_path, filename)
    logger.info('Downloading archive to: {0}'.format(output_path))
    conn.sudo('chmod 644 {0}'.format(archive_path_on_host))
    conn.get(archive_path_on_host, output_path)
    logger.info('Removing archive from host...')
    conn.sudo('rm {0}'.format(archive_path_on_host))
    output_json['archive paths'].setdefault(host_type, {})[conn.host] =\
        output_path


@logs.command(name='download',
              short_help='Download manager service logs [manager only]')
@cfy.options.output_path
@cfy.options.all_nodes
@cfy.options.common_options
@cfy.pass_logger
def download(output_path, all_nodes, logger):
    """Download an archive containing all of the manager's service logs
    """
    output_json = {'archive paths': {}}

    if not output_path:
        output_path = os.getcwd()

    if not (env.profile.ssh_user and env.profile.ssh_key):
        raise CloudifyCliError('Make sure both `ssh_user` & `ssh_key` are set')
    if all_nodes:
        if not env.profile.cluster:
            raise CloudifyCliError(
                "No cluster nodes defined in this profile")
        cluster_nodes = _get_cluster_nodes()
        for node in cluster_nodes:
            try:
                with env.ssh_connection(
                        host=node['host_ip'],
                        user=node.get('ssh_user'),
                        key=node.get('ssh_key')) as conn:
                    _download_archive(
                        conn,
                        node.get('host_type'),
                        output_path,
                        logger,
                        output_json,
                        node['host_ip'])
            except CloudifyCliError as e:
                logger.info('Skipping node {0}: {1}'
                            .format(node['hostname'], e))
    else:
        with env.ssh_connection() as conn:
            _download_archive(
                conn,
                CloudifyNodeType.MANAGER,
                output_path,
                logger,
                output_json,
                env.profile.manager_ip)

    if get_global_json_output():
        output(json.dumps(output_json, cls=CloudifyJSONEncoder))


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

    logger.info('Purging manager logs...')
    with env.ssh_connection() as conn:
        # truncate and not delete: running services can keep their open fds
        conn.run(
            'for f in $(sudo find /var/log/cloudify -name "*" -type f); '
            'do sudo truncate -s 0 $f; '
            'done'
        )


@logs.command(name='backup',
              short_help='Backup manager service logs [manager only]')
@cfy.options.common_options
@cfy.pass_logger
def backup(logger):
    """Create a backup of all logs under a single archive and save it
    on the manager under /var/log.
    """
    with env.ssh_connection() as conn:
        archive_path_on_manager = _archive_logs(
            conn, CloudifyNodeType.MANAGER, logger, env.profile.manager_ip)
        logger.info('Backing up manager logs to /var/log/{0}'.format(
            os.path.basename(archive_path_on_manager)))
        conn.sudo('mv {0} {1}'.format(archive_path_on_manager, '/var/log/'))
