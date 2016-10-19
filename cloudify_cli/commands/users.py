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
from .. import table
from ..cli import cfy


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
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by, descending, logger, client):
    """List all users
    """
    logger.info('Listing all users...')
    users_list = client.users.list(sort=sort_by, is_descending=descending)
    _print_users(users_list, 'Users:')


@users.command(name='create', short_help='Create a user [manager only]')
@cfy.argument('username')
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


@users.command(name='add-to-group',
               short_help='Add a user to a security group [manager only]')
@cfy.argument('username')
@cfy.options.group_name
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_to_group(username, group_name, logger, client):
    """Add a user to a group

    `USERNAME` is the username of the user
    """
    client.users.add_to_group(username, group_name)
    logger.info('User `{0}` added successfully to group '
                '`{1}`'.format(username, group_name))


@users.command(name='remove-from-group',
               short_help='Remove a user from a security group [manager only]')
@cfy.argument('username')
@cfy.options.group_name
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def remove_from_group(username, group_name, logger, client):
    """Remove a user from a group

    `USERNAME` is the username of the user
    """
    client.users.remove_from_group(username, group_name)
    logger.info('User `{0}` removed successfully from group '
                '`{1}`'.format(username, group_name))


@users.command(name='set-password',
               short_help='Set a new password for a user [manager only]')
@cfy.argument('username')
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
@cfy.argument('username')
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
@cfy.argument('username')
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get(username, logger, client):
    """Get details for a single user

    `USERNAME` is the username of the user
    """
    logger.info('Getting info for user `{0}`...'.format(username))
    user_details = client.users.get(username)
    _print_users([user_details], 'Requested user info:')


def _print_users(users_list, header_text):
    columns = [
        'username',
        'groups',
        'role',
        'tenants',
        'active',
        'last_login_at'
    ]
    pt = table.generate(columns, data=users_list)
    table.log(header_text, pt)
