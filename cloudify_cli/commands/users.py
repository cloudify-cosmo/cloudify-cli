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

USER_COLUMNS = ['username', 'groups', 'role', 'tenants', 'active',
                'last_login_at']


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
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by, descending, get_data, logger, client):
    """List all users
    """
    logger.info('Listing all users...')
    users_list = client.users.list(
        sort=sort_by,
        is_descending=descending,
        _get_data=get_data
    )
    print_data(USER_COLUMNS, users_list, 'Users:')


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
    user_details = client.users.get(username, _get_data=get_data)
    print_data(USER_COLUMNS, user_details, 'Requested user info:')


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
