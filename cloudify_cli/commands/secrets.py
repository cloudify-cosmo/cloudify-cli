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

from cloudify_rest_client.constants import VISIBILITY_EXCEPT_PRIVATE

from .. import env
from ..cli import cfy
from ..exceptions import CloudifyCliError
from ..table import print_data, print_details
from ..utils import (handle_client_error,
                     prettify_client_error,
                     validate_visibility)

SECRETS_COLUMNS = ['key', 'created_at', 'updated_at', 'visibility',
                   'tenant_name', 'created_by']


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
@cfy.options.secret_string
@cfy.options.secret_file
@cfy.options.secret_update_if_exists
@cfy.options.visibility(mutually_exclusive_required=False)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def create(key,
           secret_string,
           secret_file,
           update_if_exists,
           visibility,
           logger,
           client):
    """Create a new secret (key-value pair)

    `KEY` is the new secret's key
    """
    validate_visibility(visibility)
    if secret_string and secret_file:
        raise CloudifyCliError('Failed to create secret key. '
                               'The command can only accept either'
                               ' --secret-string or secret-file.')
    if secret_file:
        if not os.path.exists(secret_file):
            raise CloudifyCliError('Failed to create secret key. '
                                   'File does not exist: '
                                   '{0}'.format(secret_file))
        with open(secret_file, 'r') as secret_file:
            secret_string = secret_file.read()
    if not secret_string:
        raise CloudifyCliError('Failed to create secret key. '
                               'Missing option '
                               '--secret-string or secret-file.')

    client.secrets.create(key,
                          secret_string,
                          update_if_exists,
                          visibility)

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
        secret_details.pop('private_resource')
        print_details(secret_details, 'Requested secret info:')


@secrets.command(name='update', short_help='Update an existing secret')
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.secret_string
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def update(key, secret_string, logger, client):
    """Update an existing secret

    `KEY` is the secret's key
    """
    graceful_msg = 'Requested secret with key `{0}` was not found'.format(key)
    with handle_client_error(404, graceful_msg, logger):
        client.secrets.update(key, secret_string)
        logger.info('Secret `{0}` updated'.format(key))


@secrets.command(name='list', short_help="List all secrets")
@cfy.options.sort_by('key')
@cfy.options.descending
@cfy.options.verbose()
@cfy.options.tenant_name_for_list(required=False,
                                  resource_name_for_help='secret')
@cfy.options.all_tenants
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by,
         descending,
         tenant_name,
         all_tenants,
         pagination_offset,
         pagination_size,
         logger,
         client):
    """List all secrets
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))

    logger.info('Listing all secrets...')
    secrets_list = client.secrets.list(
        sort=sort_by,
        is_descending=descending,
        _all_tenants=all_tenants,
        _offset=pagination_offset,
        _size=pagination_size
    )
    print_data(SECRETS_COLUMNS, secrets_list, 'Secrets:')
    total = secrets_list.metadata.pagination.total
    logger.info('Showing {0} of {1} secrets'.format(len(secrets_list), total))


@secrets.command(name='delete', short_help='Delete a secret')
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete(key, logger, client):
    """Delete a secret

    `KEY` is the secret's key
    """
    graceful_msg = 'Requested secret with key `{0}` was not found'.format(key)
    with handle_client_error(404, graceful_msg, logger):
        logger.info('Deleting secret `{0}`...'.format(key))
        client.secrets.delete(key)
        logger.info('Secret removed')


@secrets.command(name='set-global',
                 short_help="Set the secret's visibility to global")
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_global(key, logger, client):
    """Set the secret's visibility to global

    `KEY` is the secret's key
    """
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        client.secrets.set_global(key)
        logger.info('Secret `{0}` was set to global'.format(key))
        logger.info("This command will be deprecated soon, please use the "
                    "'set-visibility' command instead")


@secrets.command(name='set-visibility',
                 short_help="Set the secret's visibility")
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.visibility(required=True,
                        valid_values=VISIBILITY_EXCEPT_PRIVATE,
                        mutually_exclusive_required=False)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_visibility(key, visibility, logger, client):
    """Set the secret's visibility

    `KEY` is the secret's key
    """
    validate_visibility(visibility, valid_values=VISIBILITY_EXCEPT_PRIVATE)
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        client.secrets.set_visibility(key, visibility)
        logger.info('Secret `{0}` was set to {1}'.format(key, visibility))
