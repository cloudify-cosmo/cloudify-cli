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

"""
Handles 'cfy ssh'
"""

import platform
from distutils import spawn
import re

from cloudify_cli import utils
from cloudify_cli.ssh import run_command_on_manager
from cloudify_cli import messages
from cloudify_cli.logger import get_logger
from cloudify_cli.exceptions import CloudifyCliError


def _verify_tmux_exists_on_manager(host_string):
    try:
        run_command_on_manager('which tmux', host_string=host_string)
    except:
        raise CloudifyCliError(
            'tmux executable not found on Manager {0}.\n'
            'Please verify that tmux is installed and in PATH before '
            'attempting to use shared SSH sessions.\n'
            'You can run `cfy ssh -c "sudo yum install tmux -y"` to try and '
            'install tmux on the Manager.'.format(
                host_string.split('@')[1]))


def _send_keys(logger, command, sid, host_string):
    logger.debug('Sending "{0}" to session...'.format(command))
    run_command_on_manager(
        'tmux send-keys -t {0} \'{1}\' C-m'.format(sid, command),
        host_string=host_string)


def _validate_env(ssh_command, host_session, sid, list_sessions):
    if not isinstance(ssh_command, str):
        raise CloudifyCliError('ssh_command should be a string.')
    if not isinstance(host_session, bool):
        raise CloudifyCliError('host_session should be a boolean.')
    if not isinstance(sid, str):
        raise CloudifyCliError('sid should be a str.')
    if not isinstance(list_sessions, bool):
        raise CloudifyCliError('list_sessions should be a boolean.')

    ssh_path = spawn.find_executable('ssh')
    if not ssh_path:
        raise CloudifyCliError(messages.SSH_LINUX_NOT_FOUND)

    if not ssh_path and platform.system() == 'Windows':
        raise CloudifyCliError(messages.SSH_WIN_NOT_FOUND)

    if any([host_session and sid,
            host_session and list_sessions,
            sid and list_sessions]):
        raise CloudifyCliError(messages.SSH_ARGS_CONFLICT)


def _join_session(logger, sid, host_string):
    logger.info('Attempting to join session...')
    if sid not in _get_sessions_list(logger, host_string):
        logger.error('Session {0} does not exist.'.format(sid))
        return
    run_command_on_manager(
        'tmux attach -t {0}'.format(sid),
        open_shell=True,
        host_string=host_string)


def _get_all_sessions(logger, host_string):
    logger.info('Retrieving list of existing sessions...')
    try:
        # TODO: apply tmux formatting
        output = run_command_on_manager(
            'tmux list-sessions',
            host_string=host_string)
    except:
        return None
    return output


def _get_sessions_list(logger, host_string):
    return re.findall(
        r'ssh_session_\w{6}',
        _get_all_sessions(logger, host_string))


def ssh(ssh_command, host_session, sid, list_sessions):
    """Connects to a running Manager via SSH.

    `host_session` starts a tmux session (e.g. tmux new -s
    "ssh_session_vi120m") after which a command for a client is printed
    in the tmux session for the host to send to the client
    (i.e. cfy ssh --sid ssh_session_vi120m).

    When starting a new session, the host creates an alias for "exit"
    so that when a client connects and exits, it will run "tmux detach"
    instead and not kill the session.

    When the host exits the tmux session, a command will be executed
    to kill the session.

    Passing an `ssh_command` will simply execute it on the manager while
    omitting a command will connect to an interactive shell.
    """
    _validate_env(ssh_command, host_session, sid, list_sessions)
    host_string = utils.build_manager_host_string()
    if host_session or sid or list_sessions:
        _verify_tmux_exists_on_manager(host_string)

    logger = get_logger()
    logger.info('Connecting to {0}...'.format(host_string))
    if host_session:
        sid = 'ssh_session_' + utils.generate_random_string()
        logger.info('Creating session: {0}...'.format(sid))
        try:
            run_command_on_manager(
                'tmux new -d -A -s {0}'.format(sid),
                host_string=host_string)
            logger.info('Preparing environment...')
            _send_keys(logger, 'alias exit="tmux detach"; clear', sid,
                       host_string=host_string)
            _send_keys(logger, '#Clients should run cfy ssh --sid {0} '
                       'to join the session.'.format(sid), sid,
                       host_string=host_string)
            _join_session(logger, sid, host_string)
        except Exception as ex:
            logger.error('Failed to create session ({0}).'.format(ex))
        logger.info('Killing session: {0}...'.format(sid))
        try:
            run_command_on_manager(
                'tmux kill-session -t {0}'.format(sid),
                host_string=host_string)
        except Exception as ex:
            logger.warn('Failed to kill session ({0}).'.format(ex))
    elif sid:
        _join_session(logger, sid, host_string)
    elif list_sessions:
        sessions = _get_all_sessions(logger, host_string)
        if sessions:
            logger.info('Available Sessions are:\n{0}'.format(sessions.stdout))
        else:
            logger.info('No sessions are available.')
    else:
        if ssh_command:
            logger.info('Executing command {0}...'.format(ssh_command))
        run_command_on_manager(
            ssh_command,
            open_shell=not ssh_command,
            host_string=host_string,
            force_output=True)
