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

from StringIO import StringIO

import click

from ..utils import get_version_data
from ..utils import get_manager_version_data


def _format_version_data(version_data,
                         prefix=None,
                         suffix=None,
                         infix=None):
    all_data = version_data.copy()
    all_data['prefix'] = prefix or ''
    all_data['suffix'] = suffix or ''
    all_data['infix'] = infix or ''
    output = StringIO()
    output.write('{prefix}{version}'.format(**all_data))
    output.write('{suffix}'.format(**all_data))
    return output.getvalue()


def version(ctx, param, value):
    # The callback in the `main` group is called regardless of whether
    # the --version flag was set or not so we need to return to main
    # in case it wasn't called.
    if not value or ctx.resilient_parsing:
        return

    cli_version_data = get_version_data()
    rest_version_data = get_manager_version_data()

    cli_version = _format_version_data(
        cli_version_data,
        prefix='Cloudify CLI ',
        infix=' ' * 5,
        suffix='\n')
    rest_version = ''
    if rest_version_data:
        rest_version = _format_version_data(
            rest_version_data,
            prefix='Cloudify Manager ',
            infix=' ',
            suffix=' [ip={ip}]\n'.format(**rest_version_data))
    click.echo('{0}{1}'.format(cli_version, rest_version))
    ctx.exit()
