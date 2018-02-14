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

USER_COLUMNS = ['username', 'groups', 'role', 'group_system_roles', 'active',
                'last_login_at']
GET_DATA_COLUMNS = ['user_tenants', 'group_tenants']
NO_GET_DATA_COLUMNS = ['tenants']
USER_LABELS = {'role': 'system wide role',
               'group_system_roles': 'system wide roles via groups'}


def _format_user(user):
    user_tenants = dict(
        (str(tenant), str(user.user_tenants[tenant]))
        for tenant in user.user_tenants
    )
    group_tenants = dict(
        (str(tenant),
         dict(
             (str(role),
              [str(group) for group in user.group_tenants[tenant][role]])
             for role in user.group_tenants[tenant]
         ))
        for tenant in user.group_tenants
    )
    user['user_tenants'] = str(user_tenants)[1:-1]
    user['group_tenants'] = str(group_tenants)[1:-1]
    return user


def _format_group_system_roles(user):
    group_system_roles = dict(
        (str(role),
         [str(user_group) for user_group in user['group_system_roles'][role]])
        for role in user['group_system_roles']
    )
    user['group_system_roles'] = str(group_system_roles).strip('{}')
    return user


@cfy.group(name='users')
@cfy.options.verbose()
def users():
    """Handle Cloudify users
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@users.command(name='list', short_help='List users [manager only]')
@cfy.options.sort_by('username')
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
    """List all users
    """
    logger.info('Listing all users...')
    users_list = client.users.list(
        sort=sort_by,
        is_descending=descending,
        _get_data=get_data,
        _offset=pagination_offset,
        _size=pagination_size
    )
    total = users_list.metadata.pagination.total
    # copy list
    columns = [] + USER_COLUMNS
    users_list = [_format_group_system_roles(user) for user in users_list]
    if get_data:
        users_list = [_format_user(user) for user in users_list]
        columns += GET_DATA_COLUMNS
    else:
        columns += NO_GET_DATA_COLUMNS
    print_data(columns, users_list, 'Users:', labels=USER_LABELS)
    logger.info('Showing {0} of {1} users'.format(len(users_list), total))


@users.command(name='create', short_help='Create a user [manager only]')
@cfy.argument('username', callback=cfy.validate_name)
@cfy.options.verbose()
@cfy.options.security_role
@cfy.options.password
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def create(username, security_role, password, logger, client):
    """Create a new user on the manager

    `USERNAME` is the username of the user
    """
    client.users.create(username, password, security_role)
    logger.info('User `{0}` created'.format(username))


@users.command(name='set-password',
               short_help='Set a new password for a user [manager only]')
@cfy.argument('username', callback=cfy.validate_name)
@cfy.options.password
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def set_password(username, password, logger, client):
    """Set a new password for a user

    `USERNAME` is the username of the user
    """
    logger.info('Setting new password for user {0}...'.format(username))
    client.users.set_password(username, password)
    logger.info('New password set')


@users.command(name='set-role',
               short_help='Set a new role for a user [manager only]')
@cfy.argument('username', callback=cfy.validate_name)
@cfy.options.security_role
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def set_role(username, security_role, logger, client):
    """Set a new role for a user

    `USERNAME` is the username of the user
    """
    logger.info('Setting new role for user {0}...'.format(username))
    client.users.set_role(username, security_role)
    logger.info('New role `{0}` set'.format(security_role))


@users.command(name='get',
               short_help='Get details for a single user [manager only]')
@cfy.argument(
    'username', callback=cfy.validate_name, default=env.get_username())
@cfy.options.verbose()
@cfy.options.get_data
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get(username, get_data, logger, client):
    """Get details for a single user

    `USERNAME` is the username of the user. (default: current user)
    """
    logger.info('Getting info for user `{0}`...'.format(username))
    if username == env.get_username():
        user_details = client.users.get_self(_get_data=get_data)
    else:
        user_details = client.users.get(username, _get_data=get_data)
        # copy list
    columns = [] + USER_COLUMNS
    if get_data:
        _format_user(user_details)
        columns += GET_DATA_COLUMNS
    else:
        columns += NO_GET_DATA_COLUMNS
    print_data(columns,
               user_details,
               'Requested user info:',
               labels=USER_LABELS)


@users.command(name='delete',
               short_help='Delete a user [manager only]')
@cfy.argument('username', callback=cfy.validate_name)
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete(username, logger, client):
    """Delete a user

    `USERNAME` is the username of the user
    """
    logger.info('Deleting user `{0}`...'.format(username))
    client.users.delete(username)
    logger.info('User removed')


@users.command(name='activate',
               short_help='Make an inactive user active [manager only]')
@cfy.argument('username')
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def activate(username, logger, client):
    """Activate a user

    `USERNAME` is the username of the user
    """
    graceful_msg = 'User `{0}` is already active'.format(username)
    logger.info('Activating user `{0}`...'.format(username))
    with handle_client_error(409, graceful_msg, logger):
        client.users.activate(username)
        logger.info('User activated')


@users.command(name='deactivate',
               short_help='Make an active user inactive [manager only]')
@cfy.argument('username')
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def deactivate(username, logger, client):
    """Deactivate a user

    `USERNAME` is the username of the user
    """
    graceful_msg = 'User `{0}` is already inactive'.format(username)
    logger.info('Deactivating user `{0}`...'.format(username))
    with handle_client_error(409, graceful_msg, logger):
        client.users.deactivate(username)
        logger.info('User deactivated')
