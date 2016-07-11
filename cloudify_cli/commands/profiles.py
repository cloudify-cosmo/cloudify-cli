########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
#    * limitations under the License.
import os

import click

from .. import utils
from ..config import cfy
from ..logger import get_logger


@cfy.group(name='profiles')
@cfy.options.show_active
def profiles():
    """Handle Cloudify CLI profiles

    Each profile can manage a single Cloudify manager.

    A profile is automatically created when using the `cfy use`
    and `cfy bootstrap` commands. Profiles are named according to
    the IP of the manager they manage.
    """
    pass


@profiles.command(name='list')
def list():
    """List all profiles
    """
    # TODO: consider saving profile information in a TinyDB json file for
    # easy querying and management.
    # TODO: should profiles include the local profile?
    logger = get_logger()

    current_profile = utils.get_active_profile()
    profiles = []

    logger.info('Listing all profiles...')

    excluded = ['active.profile', 'local']
    profiles_names = [item for item in os.listdir(utils.PROFILES_DIR)
                      if item not in excluded]

    for profile in profiles_names:
        profiles.append(utils.get_profile(profile))

    utils.set_active_profile(current_profile)

    pt = utils.table(
        ['manager_ip',
         'alias',
         'ssh_user',
         'ssh_key_path'],
        profiles)
    utils.print_table('Profiles:', pt)


@profiles.command(name='delete')
@click.argument('profile-name')
def delete(profile_name):
    """Delete a profile
    """
    logger = get_logger()

    logger.info('Deleting profile {0}...'.format(profile_name))

    if utils.is_profile_exists(profile_name):
        utils.delete_profile(profile_name)
        logger.info('Profile deleted')
    else:
        logger.info('Profile does not exist')


# TODO: add `cfy profiles configure` to attach key, user, etc to a profile
# TODO: add `cfy profiles export` (all or specific profile)
# TODO: add `cfy profiles import` (all or specific profile)
