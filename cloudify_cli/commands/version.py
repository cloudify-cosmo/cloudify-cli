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
Handles 'cfy --version'
"""

import argparse
import socket

from StringIO import StringIO
from cloudify_cli import utils
from cloudify_cli.utils import load_cloudify_working_dir_settings
from cloudify_cli.utils import get_version_data
from cloudify_cli.utils import get_rest_client
from cloudify_rest_client.exceptions import CloudifyClientError


class VersionAction(argparse.Action):
    def __init__(self,
                 option_strings,
                 dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS,
                 help=None):
        super(VersionAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)

    @staticmethod
    def _format_version_data(version_data, prefix=None, suffix=None,
                             infix=None):
        all_data = version_data.copy()
        all_data['prefix'] = prefix or ''
        all_data['suffix'] = suffix or ''
        all_data['infix'] = infix or ''
        output = StringIO()
        output.write('{prefix}{version}'.format(**all_data))
        if version_data['build']:
            output.write('{infix}(build: {build}, date: {date})'.format(
                **all_data))
        output.write('{suffix}'.format(**all_data))
        return output.getvalue()

    def _get_manager_version_data(self):
        dir_settings = load_cloudify_working_dir_settings(suppress_error=True)
        if not (dir_settings and dir_settings.get_management_server()):
            return None
        management_ip = dir_settings.get_management_server()
        if not self._connected_to_manager(management_ip):
            return None
        client = get_rest_client(management_ip)
        try:
            version_data = client.manager.get_version()
        except CloudifyClientError:
            return None
        version_data['ip'] = management_ip
        return version_data

    @staticmethod
    def _connected_to_manager(management_ip):
        port = utils.get_rest_port()
        try:
            sock = socket.create_connection((management_ip, port), 5)
            sock.close()
            return True
        except socket.error:
            return False

    def __call__(self, parser, namespace, values, option_string=None):
        cli_version_data = get_version_data()
        rest_version_data = self._get_manager_version_data()
        cli_version = self._format_version_data(
            cli_version_data,
            prefix='Cloudify CLI ',
            infix=' ' * 5,
            suffix='\n')
        rest_version = ''
        if rest_version_data:
            rest_version = self._format_version_data(
                rest_version_data,
                prefix='Cloudify Manager ',
                infix=' ',
                suffix=' [ip={ip}]\n'.format(**rest_version_data))
        parser.exit(message='{0}{1}'.format(cli_version,
                                            rest_version))
