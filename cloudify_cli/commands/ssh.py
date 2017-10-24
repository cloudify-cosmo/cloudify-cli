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
import re
import platform
import subprocess
from distutils import spawn

from .. import env
from .. import utils
from ..cli import cfy
from ..exceptions import CloudifyCliError
from ..ssh import run_command_on_manager, test_profile


@cfy.command(name='ssh', short_help='Connect using SSH [manager only]')
@cfy.options.ssh_command
@cfy.options.host_session
@cfy.options.session_id
@cfy.options.list_sessions
@cfy.options.verbose()
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
    _validate_env(command, host, sid, list_sessions)
    host_string = env.build_manager_host_string()
    if host or sid or list_sessions:
        _verify_tmux_exists_on_manager(host_string)

    logger.info('Connecting to {0}...'.format(host_string))
    if host:
        sid = 'ssh_session_' + utils.generate_random_string()
        logger.info('Creating session {0}...'.format(sid))
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
            logger.error('Failed to create session ({0})'.format(ex))
        logger.info('Killing session {0}...'.format(sid))
        try:
            run_command_on_manager(
                'tmux kill-session -t {0}'.format(sid),
                host_string=host_string)
        except Exception as ex:
            logger.warn('Failed to kill session ({0})'.format(ex))
    elif sid:
        _join_session(logger, sid, host_string)
    elif list_sessions:
        sessions = _get_all_sessions(logger, host_string)
        if sessions:
            logger.info('Available Sessions are:\n{0}'.format(sessions.stdout))
        else:
            logger.info('No sessions are available')
    else:
        if command:
            logger.info('Executing command {0}...'.format(command))
            run_command_on_manager(
                command,
                host_string=host_string,
                force_output=True)
        else:
            _open_interactive_shell(host_string=host_string)


def _open_interactive_shell(host_string, command=''):
    """Used as fabric's open_shell=True doesn't work well.
    (Disfigures coloring and such...)
    """
    profile = env.profile
    ssh_key_path = os.path.expanduser(profile.ssh_key)
    port = profile.ssh_port
    cmd = ['ssh', '-t', host_string, '-i', ssh_key_path, '-p', port]
    if command:
        cmd.append(command)
    subprocess.call(cmd)


def _verify_tmux_exists_on_manager(host_string):
    try:
        run_command_on_manager('which tmux', host_string=host_string)
    except Exception:
        raise CloudifyCliError(
            'tmux executable not found on manager {0}.\n'
            'Please verify that tmux is installed and in PATH before '
            'attempting to use shared SSH sessions.\n'
            'You can run `cfy ssh -c "sudo yum install tmux -y"` to try and '
            'install tmux on the manager.'.format(
                host_string.split('@')[1]))


def _send_keys(logger, command, sid, host_string):
    logger.debug('Sending "{0}" to session...'.format(command))
    run_command_on_manager(
        'tmux send-keys -t {0} \'{1}\' C-m'.format(sid, command),
        host_string=host_string)


def _validate_env(command, host, sid, list_sessions):
    ssh_path = spawn.find_executable('ssh')
    if not ssh_path:
        raise CloudifyCliError(
            "ssh not found. Possible reasons:\n"
            "1) You don't have ssh installed (try installing OpenSSH)\n"
            "2) Your PATH variable is not configured correctly\n"
            "3) You are running this command with Sudo which can manipulate "
            "environment variables for security reasons")

    if not ssh_path and platform.system() == 'Windows':
        raise CloudifyCliError(
            "ssh.exe not found. Are you sure you have it installed? "
            "As an alternative, you can use PuTTY to ssh into the manager. "
            "Do not forget to convert your private key from OpenSSH format to "
            "PuTTY's format using PuTTYGen.")

    if any([host and sid,
            host and list_sessions,
            sid and list_sessions]):
        raise CloudifyCliError(
            'Choose one of --host, --list-sessions, --sid arguments.')

    test_profile()


def _join_session(logger, sid, host_string):
    logger.info('Attempting to join session...')
    if sid not in _get_sessions_list(logger, host_string):
        logger.error('Session {0} does not exist'.format(sid))
        return
    _open_interactive_shell(
        command='tmux attach -t {0}'.format(sid),
        host_string=host_string)


def _get_all_sessions(logger, host_string):
    logger.info('Retrieving list of existing sessions...')
    try:
        output = run_command_on_manager(
            'tmux list-sessions',
            host_string=host_string)
    except Exception:
        return None
    return output


def _get_sessions_list(logger, host_string):
    return re.findall(
        r'ssh_session_\w{6}',
        _get_all_sessions(logger, host_string))
