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

import re


from .. import env
from .. import utils
from ..cli import cfy
from ..exceptions import CloudifyCliError

try:
    from invoke.exceptions import UnexpectedExit
except ImportError:
    UnexpectedExit = Exception


@cfy.command(name='ssh', short_help='Connect using SSH [manager only]')
@cfy.options.ssh_command
@cfy.options.host_session
@cfy.options.session_id
@cfy.options.list_sessions
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_logger
def ssh(command, host, sid, list_sessions, logger):
    """Connects to a running manager via SSH.

    `host` starts a tmux session (e.g. tmux new -s
    "ssh_session_vi120m") after which a command for a client is printed
    in the tmux session for the host to send to the client
    (i.e. cfy ssh --sid ssh_session_vi120m).

    When starting a new session, the host creates an alias for "exit"
    so that when a client connects and exits, it will run "tmux detach"
    instead and not kill the session.

    When the host exits the tmux session, a command will be executed
    to kill the session.

    Passing an `command` will simply execute it on the manager while
    omitting a command will connect to an interactive shell.
    """

    if any([host and sid,
            host and list_sessions,
            sid and list_sessions]):
        raise CloudifyCliError(
            'Choose one of --host, --list-sessions, --sid arguments.')

    with env.ssh_connection() as c:
        if host or sid or list_sessions:
            _verify_tmux_exists_on_manager(c)

        if host:
            _create_session(c, sid, logger)
        elif sid:
            _join_session(c, sid, logger)
        elif list_sessions:
            sessions = _get_all_sessions(c, logger)
            if sessions:
                logger.info('Available Sessions are:\n{0}'
                            .format(sessions.stdout))
            else:
                logger.info('No sessions are available')
        elif command:
            logger.debug('Executing command {0}...'.format(command))
            c.run(command)
        else:
            c.run('/bin/bash', pty=True, shell=False)


def _verify_tmux_exists_on_manager(conn):
    try:
        conn.run('which tmux')
    except UnexpectedExit:
        raise CloudifyCliError(
            'tmux not found on the manager.\n'
            'Please verify that tmux is installed and in PATH before '
            'attempting to use shared SSH sessions.\n'
            'You can run `cfy ssh -c "sudo yum install tmux -y"` to try and '
            'install tmux on the manager.')


def _send_keys(conn, logger, command, sid):
    conn.run('tmux send-keys -t {0} \'{1}\' C-m'.format(sid, command))


def _create_session(conn, sid, logger):
    sid = 'ssh_session_' + utils.generate_random_string()
    logger.info('Creating session {0}...'.format(sid))
    try:
        conn.run('tmux new -d -A -s {0}'.format(sid), pty=True)
        logger.info('Preparing environment...')
        _send_keys(conn, sid, 'alias exit="tmux detach"; clear')
        _send_keys(conn, sid,
                   '#Clients should run cfy ssh --sid {0} to join the '
                   'session.'.format(sid))
        _join_session(conn, sid, logger)
    except Exception as ex:
        logger.error('Failed to create session ({0})'.format(ex))
    logger.info('Killing session {0}...'.format(sid))
    try:
        conn.run('tmux kill-session -t {0}'.format(sid), hide=True)
    except Exception as ex:
        logger.warn('Failed to kill session ({0})'.format(ex))


def _join_session(conn, sid, logger):
    logger.info('Attempting to join session...')
    if sid not in _get_sessions_list(conn, logger):
        logger.error('Session {0} does not exist'.format(sid))
        return
    conn.run('tmux attach -t {0}'.format(sid), pty=True)


def _get_all_sessions(conn, logger):
    logger.info('Retrieving list of existing sessions...')
    try:
        output = conn.run('tmux list-sessions')
    except Exception:
        return None
    return output.stdout


def _get_sessions_list(conn, logger):
    return re.findall(
        r'ssh_session_\w{6}',
        _get_all_sessions(conn, logger))
