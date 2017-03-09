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

from .. import env
from ..cli import cfy
from ..table import print_data
from ..utils import handle_client_error

SECRETS_COLUMNS = ['key', 'value', 'created_at', 'updated_at']


@cfy.group(name='secrets')
@cfy.options.verbose()
def secrets():
    """Handle Cloudify secrets (key-value pairs)
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@secrets.command(name='create', short_help='Create a new secret '
                                           '(key-value pair)')
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.secret_value
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def create(key, secret_value, logger, client):
    """Create a new secret (key-value pair)

    `KEY` is the new secret's key
    """

    graceful_msg = 'Secret with key `{0}` is already exist in this current ' \
                   'tenant'.format(key)

    with handle_client_error(409, graceful_msg, logger):
        client.secrets.create(key, secret_value)
        logger.info('Secret `{0}` created'.format(key))


@secrets.command(name='get', short_help='Get details for a single secret')
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def get(key, logger, client):
    """Get details for a single secret

    `KEY` is the secret's key
    """

    graceful_msg = 'Requested secret with key `{0}` was not found in this ' \
                   'tenant'.format(key)

    with handle_client_error(404, graceful_msg, logger):
        logger.info('Getting info for secret `{0}`...'.format(key))
        secret_details = client.secrets.get(key)
        print_data(SECRETS_COLUMNS, secret_details, 'Requested secret info:')


@secrets.command(name='update', short_help='Update an existing secret')
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.secret_value
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def update(key, secret_value, logger, client):
    """Update an existing secret

    `KEY` is the secret's key
    """

    graceful_msg = 'Requested secret with key `{0}` was not found'.format(key)

    with handle_client_error(404, graceful_msg, logger):
        client.secrets.update(key, secret_value)
        logger.info('Secret `{0}` updated'.format(key))
