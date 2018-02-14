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

GROUP_COLUMNS = ['name', 'role', 'tenants', 'users']


def _format_group(group):
    tenants = dict((str(tenant), str(group['tenants'][tenant]))
                   for tenant in group['tenants'])
    group['tenants'] = str(tenants).strip('{}')
    return group


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
    """List all user groups
    """
    logger.info('Listing all user groups...')
    user_groups_list = client.user_groups.list(
        sort=sort_by,
        is_descending=descending,
        _get_data=get_data,
        _offset=pagination_offset,
        _size=pagination_size
    )
    total = user_groups_list.metadata.pagination.total
    if get_data:
        user_groups_list = [_format_group(group) for group in user_groups_list]
    print_data(GROUP_COLUMNS, user_groups_list, 'User groups:')
    logger.info('Showing {0} of {1} user groups'.format(len(user_groups_list),
                                                        total))


@user_groups.command(name='create',
                     short_help='Create a user group [manager only]')
@cfy.argument('user-group-name', callback=cfy.validate_name)
@cfy.options.ldap_distinguished_name
@cfy.options.security_role
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def create(user_group_name,
           ldap_distinguished_name,
           security_role,
           logger,
           client):
    """Create a new user group on the manager

    `USER_GROUP_NAME` is the name of the new user group
    """
    client.user_groups.create(user_group_name,
                              security_role,
                              ldap_group_dn=ldap_distinguished_name)
    logger.info('Group `{0}` created'.format(user_group_name))


@user_groups.command(name='get',
                     short_help='Get details for a single '
                                'user group [manager only]')
@cfy.argument('user-group-name', callback=cfy.validate_name)
@cfy.options.verbose()
@cfy.options.get_data
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get(user_group_name, get_data, logger, client):
    """Get details for a single user group

    `USER_GROUP_NAME` is the name of the user group
    """
    logger.info('Getting info for user group `{0}`...'.format(user_group_name))
    user_group_details = client.user_groups.get(
        user_group_name,
        _get_data=get_data
    )
    if get_data:
        _format_group(user_group_details)
    print_data(GROUP_COLUMNS, user_group_details, 'Requested user group info:')


@user_groups.command(name='set-role',
                     short_help='Set a new role for a group [manager only]')
@cfy.argument('user-group-name', callback=cfy.validate_name)
@cfy.options.security_role
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def set_role(user_group_name, security_role, logger, client):
    """Set a new role for a group

    `USER_GROUP_NAME` is the name of the user group
    """
    logger.info('Setting new role for group {0}...'.format(user_group_name))
    client.user_groups.set_role(user_group_name, security_role)
    logger.info('New role `{0}` set'.format(security_role))


@user_groups.command(name='add-user',
                     short_help='Add a user to a user group [manager only]')
@cfy.argument('username', callback=cfy.validate_name)
@cfy.options.group_name
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_user(username, group_name, logger, client):
    """Add a user to a user group

    `USERNAME` is the name of the user to add to the user group
    """
    graceful_msg = 'User `{0}` is already associated with ' \
                   'user group `{1}`'.format(username, group_name)
    with handle_client_error(409, graceful_msg, logger):
        client.user_groups.add_user(username, group_name)
        logger.info('User `{0}` added successfully to user group '
                    '`{1}`'.format(username, group_name))


@user_groups.command(
    name='remove-user',
    short_help='Remove a user from a user group [manager only]')
@cfy.argument('username', callback=cfy.validate_name)
@cfy.options.group_name
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def remove_user(username, group_name, logger, client):
    """Remove a user from a user group

    `USERNAME` is the name of the user to remove from the user group
    """
    graceful_msg = 'User `{0}` is not associated with ' \
                   'user group `{1}`'.format(username, group_name)
    with handle_client_error(404, graceful_msg, logger):
        client.user_groups.remove_user(username, group_name)
        logger.info('User `{0}` removed successfully from user group '
                    '`{1}`'.format(username, group_name))


@user_groups.command(name='delete',
                     short_help='Delete a user group [manager only]')
@cfy.argument('user_group-name', callback=cfy.validate_name)
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
