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
    groups_data = client.user_groups.list(sort=sort_by,
                                          is_descending=descending)

    columns = ['name']
    pt = table.generate(columns, data=groups_data)
    table.log('Groups:', pt)


@user_groups.command(name='create',
                     short_help='Create a group [manager only]')
@cfy.argument('group-name')
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def create(group_name, logger, client):
    """Create a new group on the manager

    `TENANT_NAME` is the name of the new group
    """
    client.user_groups.create(group_name)
    logger.info('Group `{0}` created'.format(group_name))
