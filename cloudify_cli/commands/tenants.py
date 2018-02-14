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

TENANT_COLUMNS = ['name', 'groups']
GET_DATA_COLUMNS = ['direct_users', 'group_users']
NO_GET_DATA_COLUMNS = ['users']
TENANT_LABELS = {'direct_users': 'direct users', 'group_users': 'group users'}


def _format_groups(groups):
    groups = dict((str(group), str(groups[group])) for group in groups)
    return str(groups).strip('{}')


def _format_users(users):
    users = dict(
        (str(user),
         [str(role) for role in users[user]['roles']])
        for user in users
    )
    return str(users).strip('{}')


def _format_direct_users(users):
    return str(
        dict((str(user), str(users[user])) for user in users)).strip('{}')


def _format_group_users(group_users):
    group_users = dict(
        (str(group),
         dict(zip(
             ('role',
              'users'),
             (str(group_users[group]['role']),
              [str(user) for user in group_users[group]['users']])
         )))
        for group in group_users
    )
    return str(group_users)[1:-1]


def _format_tenant(tenant):
    tenant['groups'] = _format_groups(tenant['groups'])
    tenant['users'] = _format_users(tenant['users'])
    tenant['direct_users'] = _format_direct_users(tenant.direct_users)
    tenant['group_users'] = _format_group_users(tenant.group_users)
    return tenant


@cfy.group(name='tenants')
@cfy.options.verbose()
def tenants():
    """Handle Cloudify tenants (Premium feature)
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@tenants.command(name='list',
                 short_help='List tenants [manager only]')
@cfy.options.sort_by('name')
@cfy.options.descending
@cfy.options.verbose()
@cfy.options.get_data
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by,
         descending,
         get_data,
         pagination_offset,
         pagination_size,
         logger,
         client):
    """List all tenants
    """
    logger.info('Listing all tenants...')
    tenants_list = client.tenants.list(
        sort=sort_by,
        is_descending=descending,
        _get_data=get_data,
        _offset=pagination_offset,
        _size=pagination_size
    )
    # copy list
    columns = [] + TENANT_COLUMNS
    if get_data:
        tenants_list = [_format_tenant(tenant) for tenant in tenants_list]
        columns += GET_DATA_COLUMNS
    else:
        columns += NO_GET_DATA_COLUMNS
    print_data(columns, tenants_list, 'Tenants:', labels=TENANT_LABELS)
    total = tenants_list.metadata.pagination.total
    logger.info('Showing {0} of {1} tenants'.format(len(tenants_list), total))


@tenants.command(name='create',
                 short_help='Create a tenant [manager only]')
@cfy.argument('tenant-name', callback=cfy.validate_name)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def create(tenant_name, logger, client):
    """Create a new tenant on the manager

    `TENANT_NAME` is the name of the new tenant
    """
    client.tenants.create(tenant_name)
    logger.info('Tenant `{0}` created'.format(tenant_name))


@tenants.command(name='add-user',
                 short_help='Add a user to a tenant [manager only]')
@cfy.argument('username', callback=cfy.validate_name)
@cfy.options.user_tenant_role()
@cfy.options.tenant_name(show_default_in_help=False)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def add_user(username, tenant_name, role, logger, client):
    """Add a user to a tenant

    `USERNAME` is the name of the user to add to the tenant
    """
    graceful_msg = (
        'User `{0}` is already associated with tenant `{1}`'
        .format(username, tenant_name)
    )
    with handle_client_error(409, graceful_msg, logger):
        client.tenants.add_user(username, tenant_name, role)
        logger.info(
            'User `{0}` added successfully to tenant `{1}`'
            .format(username, tenant_name)
        )


@tenants.command(
    name='update-user',
    short_help='Update user-tenant relationship [manager only]')
@cfy.argument('username', callback=cfy.validate_name)
@cfy.options.user_tenant_role()
@cfy.options.tenant_name(show_default_in_help=False)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def update_user(username, tenant_name, role, logger, client):
    """Update user-tenant relationship."""
    not_found_msg = (
        'User `{0}` is *not* currently associated to tenant `{1}`'
        .format(username, tenant_name)
    )
    with handle_client_error(404, not_found_msg, logger):
        client.tenants.update_user(username, tenant_name, role)
        logger.info(
            'User `{0}` updated successfully in tenant `{1}`'
            .format(username, tenant_name)
        )


@tenants.command(name='remove-user',
                 short_help='Remove a user from a tenant [manager only]')
@cfy.argument('username', callback=cfy.validate_name)
@cfy.options.tenant_name(show_default_in_help=False)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def remove_user(username, tenant_name, logger, client):
    """Remove a user from a tenant

    `USERNAME` is the name of the user to remove from the tenant
    """
    graceful_msg = 'User `{0}` is not associated with ' \
                   'tenant `{1}`'.format(username, tenant_name)
    with handle_client_error(404, graceful_msg, logger):
        client.tenants.remove_user(username, tenant_name)
        logger.info('User `{0}` removed successfully from tenant '
                    '`{1}`'.format(username, tenant_name))


@tenants.command(name='add-user-group',
                 short_help='Add a user group to a tenant [manager only]')
@cfy.argument('user-group-name', callback=cfy.validate_name)
@cfy.options.group_tenant_role()
@cfy.options.tenant_name(show_default_in_help=False)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def add_user_group(user_group_name, tenant_name, role, logger, client):
    """Add a user group to a tenant

    `USER_GROUP_NAME` is the name of the user group to add to the tenant
    """
    graceful_msg = (
        'User group `{0}` is already associated with tenant `{1}`'
        .format(user_group_name, tenant_name)
    )
    with handle_client_error(409, graceful_msg, logger):
        client.tenants.add_user_group(user_group_name, tenant_name, role)
        logger.info(
            'User group `{0}` added successfully to tenant `{1}`'
            .format(user_group_name, tenant_name)
        )


@tenants.command(
    name='update-user-group',
    short_help='Update group-tenant relationship [manager only]')
@cfy.argument('user-group-name', callback=cfy.validate_name)
@cfy.options.group_tenant_role()
@cfy.options.tenant_name(show_default_in_help=False)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def update_user_group(user_group_name, tenant_name, role, logger, client):
    """Update group-tenant relationship."""
    not_found_msg = (
        'User `{0}` is *not* currently associated to tenant `{1}`'
        .format(user_group_name, tenant_name)
    )
    with handle_client_error(404, not_found_msg, logger):
        client.tenants.update_user_group(user_group_name, tenant_name, role)
        logger.info(
            'Group `{0}` updated successfully in tenant `{1}`'
            .format(user_group_name, tenant_name)
        )


@tenants.command(name='remove-user-group',
                 short_help='Remove a user group from a tenant [manager only]')
@cfy.argument('user-group-name', callback=cfy.validate_name)
@cfy.options.tenant_name(show_default_in_help=False)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def remove_user_group(user_group_name, tenant_name, logger, client):
    """Remove a user group from a tenant

    `USER_GROUP_NAME` is the name of the user group to remove from the tenant
    """
    graceful_msg = 'User group `{0}` is not associated with ' \
                   'tenant `{1}`'.format(user_group_name, tenant_name)
    with handle_client_error(404, graceful_msg, logger):
        client.tenants.remove_user_group(user_group_name, tenant_name)
        logger.info('User group `{0}` removed successfully from tenant '
                    '`{1}`'.format(user_group_name, tenant_name))


@tenants.command(name='get',
                 short_help='Get details for a single tenant [manager only]')
@cfy.argument('tenant-name', callback=cfy.validate_name)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.options.get_data
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def get(tenant_name, get_data, logger, client):
    """Get details for a single tenant

    `TENANT_NAME` is the name of the tenant
    """
    logger.info('Getting info for tenant `{0}`...'.format(tenant_name))
    tenant_details = client.tenants.get(tenant_name, _get_data=get_data)
    # copy list
    columns = [] + TENANT_COLUMNS
    if get_data:
        _format_tenant(tenant_details)
        columns += GET_DATA_COLUMNS
    else:
        columns += NO_GET_DATA_COLUMNS
    print_data(columns,
               tenant_details,
               'Requested tenant info:',
               labels=TENANT_LABELS)


@tenants.command(name='delete',
                 short_help='Delete a tenant [manager only]')
@cfy.argument('tenant-name', callback=cfy.validate_name)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=False)
@cfy.pass_logger
def delete(tenant_name, logger, client):
    """Delete a tenant

    `TENANT_NAME` is the name of the tenant
    """
    logger.info('Deleting tenant `{0}`...'.format(tenant_name))
    client.tenants.delete(tenant_name)
    logger.info('Tenant removed')
