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

GROUP_COLUMNS = ['name', 'tenants', 'users']


@cfy.group(name='user-groups')
@cfy.options.verbose()
def user_groups():
    """Handle Cloudify user groups (Premium feature)
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@user_groups.command(name='list',
                     short_help='List user groups [manager only]')
@cfy.options.sort_by('name')
@cfy.options.descending
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by, descending, logger, client):
    """List all user groups
    """
    logger.info('Listing all user groups...')
    user_groups_list = client.user_groups.list(sort=sort_by,
                                               is_descending=descending)
    print_data(GROUP_COLUMNS, user_groups_list, 'User groups:')


@user_groups.command(name='create',
                     short_help='Create a user group [manager only]')
@cfy.argument('user-group-name')
@cfy.options.ldap_distinguished_name
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def create(user_group_name, ldap_distinguished_name, logger, client):
    """Create a new user group on the manager

    `USER_GROUP_NAME` is the name of the new user group
    """
    client.user_groups.create(user_group_name,
                              ldap_group_dn=ldap_distinguished_name)
    logger.info('Group `{0}` created'.format(user_group_name))


@user_groups.command(name='get',
                     short_help='Get details for a single '
                                'user group [manager only]')
@cfy.argument('user-group-name')
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get(user_group_name, logger, client):
    """Get details for a single user group

    `USER_GROUP_NAME` is the name of the user group
    """
    logger.info('Getting info for user group `{0}`...'.format(user_group_name))
    user_group_details = client.user_groups.get(user_group_name)
    print_data(GROUP_COLUMNS, user_group_details, 'Requested user group info:')


@user_groups.command(name='add-user',
                     short_help='Add a user to a user group [manager only]')
@cfy.argument('user-group-name')
@cfy.options.manager_username_required
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_user(user_group_name, manager_username, logger, client):
    """Add a user to a user group

    `USER_GROUP_NAME` is the name of the user group
    """
    client.users.add_to_group(manager_username, user_group_name)
    logger.info('User `{0}` added successfully to user group '
                '`{1}`'.format(manager_username, user_group_name))


@user_groups.command(
    name='remove-user',
    short_help='Remove a user from a user group [manager only]')
@cfy.argument('user-group-name')
@cfy.options.manager_username_required
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def remove_user(user_group_name, manager_username, logger, client):
    """Remove a user from a user group

    `USER_GROUP_NAME` is the name of the user group
    """
    client.users.remove_from_group(manager_username, user_group_name)
    logger.info('User `{0}` removed successfully from user group '
                '`{1}`'.format(manager_username, user_group_name))


@user_groups.command(name='delete',
                     short_help='Delete a user group [manager only]')
@cfy.argument('user_group-name')
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete(user_group_name, logger, client):
    """Delete a user group

    `USER_GROUP_NAME` is the name of the user group
    """
    logger.info('Deleting user group `{0}`...'.format(user_group_name))
    client.user_groups.delete(user_group_name)
    logger.info('User group removed')
