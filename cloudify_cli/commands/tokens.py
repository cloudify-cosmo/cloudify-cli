import click

from cloudify_cli.cli import cfy
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.table import print_single, print_data

REST_TOKEN_COLUMNS = ['id', 'role', 'description',
                      'expiration_date', 'last_used']


@cfy.group(name='tokens')
@cfy.assert_manager_active()
def tokens():
    """Handle tokens on the manager"""


@tokens.command(
    name='create',
    short_help='Create a token for this user on the Cloudify Manager')
@cfy.assert_manager_active()
@cfy.options.common_options
@click.option('-e', '--expiry',
              help="Token expiration, e.g. +10h or 2121-03-09 14:52. "
                   "Absolute times are considered to be in UTC.")
@click.option('-d', '--description', help="Token description")
@cfy.pass_client()
@cfy.pass_logger
def create(logger, client, description, expiry):
    logger.info('Listing REST tokens')
    token = client.tokens.create(expiration=expiry, description=description)
    columns = REST_TOKEN_COLUMNS + ['value']
    print_single(columns, token, 'REST token')


@tokens.command(
    name='list',
    short_help='Lists tokens from the Cloudify Manager')
@cfy.assert_manager_active()
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def list(logger, client):
    logger.info('Listing REST tokens')
    tokens = client.tokens.list()
    columns = REST_TOKEN_COLUMNS
    # An admin listing tokens will see tokens for other users
    if any(token.username != tokens[0].username
           for token in tokens):
        columns = columns + ['username']
    print_data(
        columns,
        tokens,
        'Token listing',
    )
    total = tokens.metadata.pagination.total
    logger.info('Showing %s of %s tokens', len(tokens), total)


@tokens.command(
    name='get',
    short_help='Get details of a REST token from the Cloudify Manager.')
@cfy.assert_manager_active()
@cfy.options.common_options
@cfy.argument('token_id', type=str, default=None, required=False)
@cfy.pass_client()
@cfy.pass_logger
def get(logger, client, token_id):
    if token_id is None:
        # Give a helpful error because of the back compat break
        raise CloudifyCliError(
            'Token ID must now be provided to get a token.\n'
            'For old `cfy tokens get` functionality, use `cfy tokens create`.'
        )
    logger.info('Retrieving REST token')
    token = client.tokens.get(token_id)
    print_single(REST_TOKEN_COLUMNS, token, 'REST token')


@tokens.command(
    name='delete',
    short_help='Delete a REST token from the Cloudify Manager, disabling it.')
@cfy.assert_manager_active()
@cfy.options.common_options
@cfy.argument('token_id', type=str, default=None, required=True)
@cfy.pass_client()
@cfy.pass_logger
def delete(logger, client, token_id):
    logger.info('Deleting REST token %s', token_id)
    client.tokens.delete(token_id)
