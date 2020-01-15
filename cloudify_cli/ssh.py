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

import fabric.api as fab

from .logger import get_global_verbosity
from .exceptions import CloudifyCliError
from .env import profile

SSH_ERR = '`ssh_{0}` is not set in the current profile. ' \
          'Please run `cfy profiles set --ssh-{0} <ssh-{0}>`.'


def get_host_date(host_string):
    # output here should be hidden anyway.
    with fab.settings(fab.hide('running', 'stdout')):
        return run_command_on_host('date +%Y%m%dT%H%M%S', host_string).stdout


def get_file_from_host(remote_source_path,
                       destination_path,
                       host_string,
                       key_filename=None):
    key_filename = key_filename or os.path.expanduser(profile.ssh_key)
    with fab.settings(
            fab.hide('running', 'stdout'),
            host_string=host_string,
            key_filename=key_filename,
            port=profile.ssh_port):
        fab.get(remote_source_path, destination_path)


def put_file_in_host(source_path,
                     remote_source_path,
                     host_string,
                     use_sudo=True,
                     key_filename=None,
                     port=''):
    port = port or profile.ssh_port
    if not key_filename:
        key_filename = os.path.expanduser(profile.ssh_key)
    with fab.settings(
            fab.hide('running', 'stdout'),
            host_string=host_string,
            key_filename=key_filename,
            port=port):
        fab.put(use_sudo=use_sudo,
                local_path=source_path,
                remote_path=remote_source_path)


def run_command_on_host(command,
                        host_string,
                        use_sudo=False,
                        open_shell=False,
                        force_output=False,
                        key_filename=None,
                        ignore_failure=False):
    """Runs an SSH command on a Manager.

    `open_shell` opens an interactive shell to the server.
    `host_string` can be explicitly provided to save on REST calls.
    `force_output` forces all output as if running in verbose.
    """
    test_profile()

    key_filename = key_filename or os.path.expanduser(profile.ssh_key)
    port = int(profile.ssh_port)

    def execute():

        with fab.settings(
                host_string=host_string,
                key_filename=key_filename,
                port=port,
                warn_only=True):
            if use_sudo:
                output = fab.sudo(command)
            elif open_shell:
                fab.open_shell(command)
                return None
            else:
                output = fab.run(command)
            if output.failed and not ignore_failure:
                raise CloudifyCliError(
                    'Failed to execute: {0} ({1})'.format(
                        output.real_command, output.stderr))
            return output

    if get_global_verbosity() or force_output:
        return execute()
    else:
        with fab.hide('running', 'stdout', 'stderr', 'warnings'):
            return execute()


def test_profile():
    missing_config = False
    missing_part = ''

    if not profile.ssh_user:
        missing_config = True
        missing_part = 'user'
    elif not profile.ssh_key:
        missing_config = True
        missing_part = 'key'
    elif not profile.ssh_port:
        missing_config = True
        missing_part = 'port'

    if missing_config:
        raise CloudifyCliError(SSH_ERR.format(missing_part))
