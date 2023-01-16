import os
import json

import click
from cloudify_rest_client.constants import VISIBILITY_EXCEPT_PRIVATE

from cloudify_cli import env, utils
from cloudify_cli.cli import cfy
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.table import print_data, print_details
from cloudify_cli.utils import (
    load_json,
    print_dict,
    validate_visibility,
    assert_one_argument,
    handle_client_error,
    prettify_client_error)

SECRETS_COLUMNS = [
    'key',
    'created_at',
    'updated_at',
    'visibility',
    'tenant_name',
    'created_by',
    'is_hidden_value',
    'provider_name',
]

SECRETS_PROVIDER_COLUMNS = [
    'name',
    'type',
    'visibility',
    'tenant_name',
    'created_by',
    'created_at',
]


@cfy.group(name='secrets')
@cfy.options.common_options
def secrets():
    """Handle Cloudify secrets (key-value pairs)
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@secrets.group(name='providers')
@cfy.options.common_options
def providers():
    """Handle Cloudify Secrets Providers
    """
    pass


@secrets.command(name='create', short_help='Create a new secret '
                                           '(key-value pair)')
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.secret_string
@cfy.options.secret_file()
@cfy.options.secret_update_if_exists
@cfy.options.visibility(mutually_exclusive_required=False)
@cfy.options.hidden_value
@cfy.options.secret_schema
@cfy.options.secret_flag_dict
@cfy.options.secret_flag_list
@cfy.options.tenant_name(required=False, resource_name_for_help='secret')
@cfy.options.provider_name
@cfy.options.provider_options(
    required=False,
)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def create(key,
           secret_string,
           secret_file,
           update_if_exists,
           hidden_value,
           secret_schema,
           secret_flag_dict,
           secret_flag_list,
           visibility,
           tenant_name,
           provider_name,
           provider_options,
           logger,
           client):
    """Create a new secret (key-value pair)

    `KEY` is the new secret's key
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)
    value = _get_secret_string(secret_file, secret_string)
    if not value and not provider_name:
        raise CloudifyCliError('Failed to create secret key. '
                               'Missing option '
                               '--secret-string, secret-file or provider.')

    if secret_schema:
        try:
            secret_schema = json.loads(secret_schema)
        except json.decoder.JSONDecodeError as e:
            raise CloudifyCliError(
                f'Error decoding JSON schema "{secret_schema}": {e}')
        if not isinstance(secret_schema, dict) or \
                not secret_schema.get('type'):
            raise CloudifyCliError(
                'Invalid JSON schema. Expected a dict with a "type" key')

    if secret_flag_dict:
        secret_schema = {"type": "object"}
    if secret_flag_list:
        secret_schema = {"type": "array"}

    if secret_schema and value:
        try:
            value = json.loads(value)
        except json.decoder.JSONDecodeError:
            raise CloudifyCliError(
                f'Error decoding secret value: \'{value}\' is not of '
                f'type \'{secret_schema.get("type")}\'')

    client.secrets.create(
        key,
        value,
        update_if_exists,
        hidden_value,
        visibility,
        secret_schema,
        provider_name,
        provider_options,
    )

    logger.info('Secret `{0}` created'.format(key))


@secrets.command(name='get', short_help='Get details for a single secret')
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.tenant_name(required=False, resource_name_for_help='secret')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def get(key, tenant_name, logger, client):
    """Get details for a single secret

    `KEY` is the secret's key
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = 'Requested secret with key `{0}` was not found in this ' \
                   'tenant'.format(key)
    with handle_client_error(404, graceful_msg, logger):
        logger.info('Getting info for secret `{0}`...'.format(key))
        secret_details = client.secrets.get(key)
        if secret_details.is_hidden_value and secret_details.value == '':
            secret_details.value = '*********'
        secret_details.pop('private_resource')
        secret_details.pop('resource_availability')
        print_details(secret_details, 'Requested secret info:')


@secrets.command(name='export',
                 short_help='Export secrets from the Manager to a file')
@cfy.options.encryption_passphrase
@cfy.options.visibility_filter
@cfy.options.tenant_name_for_list(required=False,
                                  resource_name_for_help='secret')
@cfy.options.non_encrypted()
@cfy.options.all_tenants
@cfy.options.filter_by
@cfy.options.output_path
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def export(tenant_name,
           all_tenants,
           filter_by,
           passphrase,
           non_encrypted,
           visibility,
           logger,
           client,
           output_path):
    """Export secrets from the Manager to a file
    """
    assert_one_argument({'passphrase': passphrase,
                         'non_encrypted': non_encrypted})
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)
    secrets_list = client.secrets.export(visibility=visibility,
                                         _passphrase=passphrase,
                                         _all_tenants=all_tenants,
                                         _search=filter_by)

    output_path = output_path if output_path else 'secrets.json'
    with open(output_path, 'w') as output_file:
        json.dump(secrets_list, output_file, indent=1)
    if not passphrase:
        logger.info('No password was given, the secrets are not encrypted')
    logger.info('The secrets` file was saved to {}'.format(output_path))


@secrets.command(name='import',
                 short_help='Import secrets from a file to the Manager')
@cfy.options.encryption_passphrase
@cfy.options.import_input_path()
@cfy.options.non_encrypted()
@cfy.options.override_collisions
@cfy.options.tenant_map
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def import_secrets(passphrase,
                   non_encrypted,
                   tenant_map,
                   override_collisions,
                   input_path,
                   logger,
                   client):
    """Import secrets from a file to the Manager
    """
    assert_one_argument({'passphrase': passphrase,
                         'non_encrypted': non_encrypted})
    secrets_list = load_json(input_path)
    tenant_map = load_json(tenant_map)
    logger.info('Importing secrets to Manager')
    response = client.secrets.import_secrets(
        secrets_list=secrets_list,
        tenant_map=tenant_map,
        passphrase=passphrase,
        override_collisions=override_collisions)
    _print_import_response(response, logger, override_collisions)


@secrets.command(name='update', short_help='Update an existing secret')
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.secret_string
@cfy.options.secret_file()
@cfy.options.update_hidden_value
@cfy.options.update_visibility
@cfy.options.tenant_name(required=False, resource_name_for_help='secret')
@cfy.options.provider_name
@cfy.options.provider_options(
    required=False,
)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def update(key,
           secret_string,
           secret_file,
           hidden_value,
           visibility,
           tenant_name,
           provider_name,
           provider_options,
           logger,
           client):
    """Update an existing secret

    `KEY` is the secret's key
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)

    if provider_name:
        client.secrets_providers.get(provider_name)

    value = _get_secret_string(secret_file, secret_string)
    graceful_msg = 'Requested secret with key `{0}` was not found'.format(key)
    with handle_client_error(404, graceful_msg, logger):
        secret_details = client.secrets.get(key)
        if secret_details.schema:
            try:
                value = json.loads(value)
            except json.decoder.JSONDecodeError:
                raise CloudifyCliError(
                    f'Error decoding secret value: \'{value}\' is not of '
                    f'type \'{secret_details.schema.get("type")}\'')

        client.secrets.update(
            key,
            value,
            visibility,
            hidden_value,
            provider_name,
            provider_options,
        )
        logger.info('Secret `{0}` updated'.format(key))


@secrets.command(name='list', short_help="List all secrets")
@cfy.options.sort_by('key')
@cfy.options.descending
@cfy.options.common_options
@cfy.options.tenant_name_for_list(required=False,
                                  resource_name_for_help='secret')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.provider_multiple()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def _list(
        sort_by,
        descending,
        tenant_name,
        all_tenants,
        search,
        pagination_offset,
        pagination_size,
        provider,
        logger,
        client,
):
    """List all secrets
    """
    filter_rules = None

    if provider:
        filter_rules = [
            {
                "key": "provider_name",
                "values": provider,
                "operator": "starts_with",
                "type": "attribute",
            }
        ]

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing all secrets...')
    secrets_list = client.secrets.list(
        sort=sort_by,
        is_descending=descending,
        filter_rules=filter_rules,
        _all_tenants=all_tenants,
        _search=search,
        _offset=pagination_offset,
        _size=pagination_size
    )
    print_data(SECRETS_COLUMNS, secrets_list, 'Secrets:')
    total = secrets_list.metadata.pagination.total
    logger.info('Showing {0} of {1} secrets'.format(len(secrets_list), total))


@secrets.command(name='delete', short_help='Delete a secret')
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.tenant_name(required=False, resource_name_for_help='secret')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete(key, tenant_name, logger, client):
    """Delete a secret

    `KEY` is the secret's key
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = 'Requested secret with key `{0}` was not found'.format(key)
    with handle_client_error(404, graceful_msg, logger):
        logger.info('Deleting secret `{0}`...'.format(key))
        client.secrets.delete(key)
        logger.info('Secret removed')


@secrets.command(name='set-global',
                 short_help="Set the secret's visibility to global")
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.common_options
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
        logger.warning("This command is deprecated and will be removed soon, "
                       "please use the 'set-visibility' command instead")


@secrets.command(name='set-visibility',
                 short_help="Set the secret's visibility")
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.visibility(required=True,
                        valid_values=VISIBILITY_EXCEPT_PRIVATE,
                        mutually_exclusive_required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='secret')
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_visibility(key, visibility, tenant_name, logger, client):
    """Set the secret's visibility

    `KEY` is the secret's key
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility, valid_values=VISIBILITY_EXCEPT_PRIVATE)
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        client.secrets.set_visibility(key, visibility)
        logger.info('Secret `{0}` was set to {1}'.format(key, visibility))


@secrets.command(name='set-owner',
                 short_help="Change secret's ownership")
@cfy.argument('key', callback=cfy.validate_name)
@cfy.options.new_username()
@cfy.options.tenant_name(required=False, resource_name_for_help='secret')
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_owner(key, username, tenant_name, logger, client):
    """Set a new owner for the secret."""
    utils.explicit_tenant_name_message(tenant_name, logger)
    secret = client.secrets.update(key, creator=username)
    logger.info('Secret `%s` is now owned by user `%s`.',
                key, secret.get('created_by'))


@providers.command(
    name='create',
    short_help='Create a new Secrets Provider',
)
@cfy.argument('secrets_provider_name')
@cfy.options.secrets_provider_type()
@cfy.options.secrets_provider_skip_check()
@cfy.options.connection_parameters(
    required=False,
)
@cfy.options.tenant_name(
    required=False,
    resource_name_for_help='Secrets Provider',
)
@cfy.options.visibility(
    mutually_exclusive_required=False,
)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(
    use_tenant_in_header=True,
)
@cfy.pass_logger
def providers_create(
        secrets_provider_name,
        secrets_provider_type,
        skip_check,
        connection_parameters,
        tenant_name,
        visibility,
        logger,
        client,
):
    client.secrets_providers.create(
        secrets_provider_name,
        secrets_provider_type,
        connection_parameters,
        visibility,
    )

    logger.info(
        'Secrets Provider `%s` created',
        secrets_provider_name,
    )

    if not skip_check:
        client.secrets_providers.check(
            name=secrets_provider_name,
        )

        logger.info(
            'Connected to the Secrets Provider successfully',
        )


@providers.command(
    name='update',
    short_help='Update an existing Secrets Provider',
)
@cfy.argument('secrets_provider_name')
@cfy.options.secrets_provider_type(
    required=False,
)
@cfy.options.connection_parameters(
    required=False,
)
@cfy.options.tenant_name(
    required=False,
    resource_name_for_help='Secrets Provider',
)
@cfy.options.visibility(
    mutually_exclusive_required=False,
)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(
    use_tenant_in_header=True,
)
@cfy.pass_logger
def providers_update(
        secrets_provider_name,
        secrets_provider_type,
        connection_parameters,
        tenant_name,
        visibility,
        logger,
        client,
):
    client.secrets_providers.update(
        secrets_provider_name,
        secrets_provider_type,
        connection_parameters,
        visibility,
    )

    logger.info(
        'Secrets Provider `%s` updated',
        secrets_provider_name,
    )


@providers.command(
    name='delete',
    short_help='Delete a Secrets Provider',
)
@cfy.argument('secrets_provider_name')
@cfy.options.tenant_name(
    required=False,
    resource_name_for_help='Secrets Provider',
)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def providers_delete(secrets_provider_name, tenant_name, logger, client):
    """Delete a Secrets Provider
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = 'Requested Secrets Provider with name `{0}` was not found' \
        .format(secrets_provider_name)

    with handle_client_error(404, graceful_msg, logger):
        logger.info(
            'Deleting Secrets Provider `%s`...',
            secrets_provider_name
        )
        client.secrets_providers.delete(secrets_provider_name)
        logger.info('Secrets Provider removed')


@providers.command(
    name='get',
    short_help='Get details for a single Secrets Provider',
)
@cfy.argument('secrets_provider_name')
@cfy.options.tenant_name(
    required=False,
    resource_name_for_help='Secrets Provider',
)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(
    use_tenant_in_header=True,
)
@cfy.pass_logger
def providers_get(secrets_provider_name, tenant_name, logger, client):
    """Get details for a single Secrets Provider
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = 'Requested Secrets Provider with name `{0}`' \
                   ' was not found in this tenant'.format(
                        secrets_provider_name
                    )
    with handle_client_error(404, graceful_msg, logger):
        logger.info(
            'Getting info for Secrets Provider `%s`...',
            secrets_provider_name,
        )
        details = client.secrets_providers.get(secrets_provider_name)

        print_details(details, 'Requested Secrets Provider info:')


@providers.command(
    name='list',
    short_help="List all Secrets Providers",
)
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
@cfy.options.common_options
def providers_list(
        logger,
        client,
):
    logger.info('Listing all Secrets Providers...')
    secrets_list = client.secrets_providers.list()
    print_data(SECRETS_PROVIDER_COLUMNS, secrets_list, 'Secrets Providers:')
    total = secrets_list.metadata.pagination.total
    logger.info(
        'Showing %s of %s Secrets Providers',
        len(secrets_list),
        total,
    )


@providers.command(
    name='test',
    short_help='Test a Secrets Provider connectivity',
)
@cfy.argument(
    'secrets_provider_name',
    required=False,
    default='',
)
@cfy.options.secrets_provider_type(
    required=False,
    default='',
    callback=None,
)
@cfy.options.connection_parameters(
    required=False,
)
@cfy.options.tenant_name(
    required=False,
    resource_name_for_help='Secrets Provider',
)
@cfy.options.visibility(
    mutually_exclusive_required=False,
)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(
    use_tenant_in_header=True,
)
@cfy.pass_logger
def providers_test(
        secrets_provider_name,
        secrets_provider_type,
        connection_parameters,
        tenant_name,
        visibility,
        logger,
        client,
):
    client.secrets_providers.check(
        name=secrets_provider_name,
        _type=secrets_provider_type,
        connection_parameters=connection_parameters,
    )

    logger.info(
        'Connected to the Secrets Provider successfully',
    )


def _get_secret_string(secret_file, secret_string):
    if secret_file:
        if not os.path.exists(secret_file):
            raise CloudifyCliError('Failed to create secret key. '
                                   'File does not exist: '
                                   '{0}'.format(secret_file))
        with open(secret_file, 'r') as secret_file:
            secret_string = secret_file.read()
    return secret_string


def _print_import_response(response, logger, override_collisions):
    logger.info('Secrets imported')
    if response['colliding_secrets']:
        if override_collisions:
            logger.info('Please note that the following secrets were '
                        'overridden:')
        else:
            logger.info('Please note that the following secrets were not '
                        'created because they collided with existing'
                        ' secrets in the mentioned tenant:')
        print_dict(response['colliding_secrets'], logger)
    if response['secrets_errors']:
        _print_secrets_errors(response['secrets_errors'], logger)


def _print_secrets_errors(secrets_errors_dict, logger):
    secrets_errors_list = sorted(
        secrets_errors_dict.items(), key=lambda item: int(item[0]))
    logger.info('\nPlease note the following secrets were not imported due'
                ' to the the errors mentioned for each secret. The secrets`'
                ' number refer to their position in the imported list:')
    for key, secret_errors in secrets_errors_list:
        click.echo('\n\tSecret {0}:'.format(int(key) + 1))
        for attr, error in secret_errors.items():
            if attr == 'missing secret fields':
                error = [str(param) for param in error]
            click.echo('\t\t{0}: {1}'.format(attr, error))
