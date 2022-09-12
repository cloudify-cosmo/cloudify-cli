import click

from cloudify_cli.cli import cfy
from cloudify_cli.table import print_data


@cfy.group(name='permissions')
@cfy.options.common_options
@cfy.assert_manager_active()
def permissions():
    pass


@permissions.command(name='list')
@click.option('--role', help='List permissions for this role')
@cfy.options.common_options
@cfy.pass_logger
@cfy.pass_client()
def list(role, logger, client):
    """List defined permissions."""
    permissions = {}
    for permission in client.permissions.list(role=role):
        permissions.setdefault(
            permission['permission'], []
        ).append(permission['role'])
    permissions = [{'permission': k, 'roles': v}
                   for k, v in permissions.items()]
    print_data(['permission', 'roles'], permissions, 'Permissions:')


@permissions.command(name='allow')
@click.option('--role', help='Allow permission for this role')
@click.option('--permission', help='Allow this permission')
@cfy.options.common_options
@cfy.pass_logger
@cfy.pass_client()
def allow(role, permission, logger, client):
    """Define a new permission."""
    client.permissions.add(permission, role)
    logger.info('Allowed role %s the permission %s', role, permission)
    logger.warning('Updating manager permissions only takes effect after '
                   'restarting the REST Service')


@permissions.command(name='disallow')
@click.option('--role', help='Disallow permission for this role')
@click.option('--permission', help='Disallow this permission')
@cfy.options.common_options
@cfy.pass_logger
@cfy.pass_client()
def disallow(role, permission, logger, client):
    """Remove a defined permission."""
    client.permissions.delete(permission, role)
    logger.info('Disallowed role %s the permission %s', role, permission)
    logger.warning('Updating manager permissions only takes effect after '
                   'restarting the REST Service')
