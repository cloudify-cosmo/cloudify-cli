########
# Copyright (c) 2019 Cloudify.co Ltd. All rights reserved
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


from cloudify_cli.cli import cfy
from cloudify_cli.table import print_data

CONFIG_COLUMNS = [
    'name', 'value', 'scope', 'updated_at', 'is_editable', 'admin_only',
]


@cfy.group(name='config')
@cfy.options.common_options
def config():
    """Handle manager configuration"""


@config.command(name='list',
                short_help='List configuration')
@cfy.pass_client()
@cfy.options.common_options
def list_config(client):
    configs = client.manager.get_config()
    print_data(CONFIG_COLUMNS, configs, 'Config:')


@config.command(name='update',
                short_help='Update configuration')
@cfy.pass_client()
@cfy.pass_logger
@cfy.argument('inputs', callback=cfy.inputs_callback, nargs=-1)
@cfy.options.common_options
def update_config(client, inputs, logger):
    """Update the manager configuration.

    Pass INPUTS as a yaml-formatted dict with {"config name": "new value"},
    or as a path to a file containing yaml.

    Note: strings passed as input must be surrounded by '...' or "..."

    To resolve ambiguous names, config name can be prefixed with scope,
    e.g.:
    cfy config update '{"rest.ldap_username": "adminuser",
    "rest.ldap_password": "adminpassword"}'

    """
    for name, value in inputs.items():
        updated = client.manager.put_config(name, value)
        logger.info('Updated %s to %s', name, value)
        if updated.scope == 'mgmtworker':
            logger.info('Updating mgmtworker config will only take effect '
                        'after the service has been restarted')
        elif updated.scope == 'agent':
            logger.info('Updating agent config will only take effect for '
                        'agents installed from now on. It will NOT update '
                        'existing agents.')
