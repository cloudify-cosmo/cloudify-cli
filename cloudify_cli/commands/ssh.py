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

import os
import platform

from distutils import spawn
from cloudify_cli import messages
from cloudify_cli.logger import get_logger
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.cli import get_global_verbosity
from cloudify_cli.utils import get_management_user
from cloudify_cli.utils import get_management_server_ip
from cloudify_cli.utils import get_management_key


def ssh(ssh_plain_mode, ssh_command):
    logger = get_logger()
    ssh_path = spawn.find_executable('ssh')
    logger.debug('SSH executable path: {0}'.format(ssh_path or 'Not found'))
    if not ssh_path and platform.system() == 'Windows':
        msg = messages.SSH_WIN_NOT_FOUND
        raise CloudifyCliError(msg)
    elif not ssh_path:
        msg = messages.SSH_LINUX_NOT_FOUND
        raise CloudifyCliError(msg)
    else:
        command = [ssh_path, '{0}@{1}'.format(get_management_user(),
                                              get_management_server_ip())]
        if get_global_verbosity():
            command.append('-v')
        if not ssh_plain_mode:
            command.extend(['-i', os.path.expanduser(get_management_key())])
        if ssh_command:
            command.extend(['--', ssh_command])
        logger.debug('executing command: {0}'.format(' '.join(command)))
        logger.info('Trying to connect...')
        from subprocess import call
        call(command)
