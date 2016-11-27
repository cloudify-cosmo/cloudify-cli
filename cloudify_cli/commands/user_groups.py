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
                     short_help='List groups [manager only]')
@cfy.options.sort_by('name')
@cfy.options.descending
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by, descending, logger, client):
    """List all groups
    """
    logger.info('Listing all groups...')
    user_groups_list = client.user_groups.list(sort=sort_by,
                                               is_descending=descending)
    print_data(GROUP_COLUMNS, user_groups_list, 'Groups:')


@user_groups.command(name='create',
                     short_help='Create a group [manager only]')
@cfy.argument('group-name')
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def create(group_name, logger, client):
    """Create a new group on the manager

    `GROUP_NAME` is the name of the new group
    """
    client.user_groups.create(group_name)
    logger.info('Group `{0}` created'.format(group_name))


@user_groups.command(name='get',
                     short_help='Get details for a single '
                                'user group [manager only]')
@cfy.argument('group-name')
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get(group_name, logger, client):
    """Get details for a single user group

    `GROUP_NAME` is the name of the group
    """
    logger.info('Getting info for user group `{0}`...'.format(group_name))
    user_group_details = client.user_groups.get(group_name)
    print_data(GROUP_COLUMNS, user_group_details, 'Requested user group info:')


@user_groups.command(
    name='add-user',
    short_help='Add a user to a users group [manager only]')
@cfy.argument('group-name')
@cfy.options.manager_username_required
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_user(group_name, manager_username, logger, client):
    """Add a user to a group

    `GROUP_NAME` is the name of the group
    """
    client.users.add_to_group(manager_username, group_name)
    logger.info('User `{0}` added successfully to group '
                '`{1}`'.format(manager_username, group_name))


@user_groups.command(
    name='remove-user',
    short_help='Remove a user from a users group [manager only]')
@cfy.argument('group-name')
@cfy.options.manager_username_required
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def remove_user(group_name, manager_username, logger, client):
    """Remove a user from a group

    `USERNAME` is the username of the user
    """
    client.users.remove_from_group(manager_username, group_name)
    logger.info('User `{0}` removed successfully from group '
                '`{1}`'.format(manager_username, group_name))
