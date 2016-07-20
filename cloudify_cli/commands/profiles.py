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
import tarfile
from contextlib import closing

from .. import utils
from .. import common
from ..config import cfy
from ..logger import get_logger
from ..exceptions import CloudifyCliError


@cfy.group(name='profiles')
@cfy.options.show_active
@cfy.options.verbose
def profiles():
    """Handle Cloudify CLI profiles

    Each profile can manage a single Cloudify manager.

    A profile is automatically created when using the `cfy use`,
    and `cfy bootstrap` commands.

    Profiles are named according to the IP of the manager they manage.
    """
    if not utils.is_initialized():
        utils.raise_uninitialized()


@profiles.command(name='list')
@cfy.options.verbose
def list():
    """List all profiles
    """
    # TODO: consider saving profile information in a TinyDB json file for
    # easy querying and management.
    logger = get_logger()

    profiles = []

    logger.info('Listing all profiles...')

    # TODO: Remove after deciding whether `local` at all exists or not.
    excluded = ['local']
    profile_names = [item for item in os.listdir(utils.PROFILES_DIR)
                     if item not in excluded]

    for profile in profile_names:
        profiles.append(utils.get_profile(profile))

    pt = utils.table(['manager_ip', 'alias', 'ssh_user', 'ssh_key_path'],
                     profiles)
    common.print_table('Profiles:', pt)

    if not profile_names:
        logger.info(
            'No profiles found. You can create a new profile '
            'by bootstrapping a manager via `cfy bootstrap` or using an '
            'existing manager via the `cfy use` command')


@profiles.command(name='delete')
@cfy.argument('profile-name')
@cfy.options.verbose
def delete(profile_name):
    """Delete a profile

    `PROFILE_NAME` is the IP of the manager the profile manages.
    """
    logger = get_logger()

    logger.info('Deleting profile {0}...'.format(profile_name))
    if utils.is_profile_exists(profile_name):
        utils.delete_profile(profile_name)
        logger.info('Profile deleted')
    else:
        logger.info('Profile does not exist')


@profiles.command(name='export')
@cfy.options.verbose
@cfy.options.optional_output_path
def export_profiles(output_path):
    """Export all profiles to a file

    If `-o / --output-path` is omitted, the archive's name will be
    `cfy-profiles.tar.gz`.
    """
    logger = get_logger()

    _assert_profiles_exist()

    destination = output_path or \
        os.path.join(os.getcwd(), 'cfy-profiles.tar.gz')

    logger.info('Exporting profiles to {0}...'.format(destination))
    _tar(utils.PROFILES_DIR, destination)
    logger.info('Export complete!')
    logger.info(
        'You can import the profiles by running '
        '`cfy profiles import PROFILES_ARCHIVE`')


@profiles.command(name='import')
@cfy.argument('archive-path')
@cfy.options.verbose
def import_profiles(archive_path):
    """Import profiles from a profiles archive

    `ARCHIVE_PATH` is the path to the profiles archive to import.

    WARNING: If a profile exists both in the archive and locally
    it will be overwritten (any other profiles will be left intact).
    """
    logger = get_logger()

    _assert_is_tarfile(archive_path)
    _assert_profiles_archive(archive_path)

    logger.info('Importing profiles from {0}...'.format(archive_path))
    _untar(archive_path, os.path.dirname(utils.PROFILES_DIR))
    logger.info('Import complete!')
    logger.info('You can list profiles using `cfy profiles list`')


def _tar(source, destination):
    logger = get_logger()
    logger.debug('Creating tgz archive: {0}...'.format(destination))
    with closing(tarfile.open(destination, 'w:gz')) as tar:
        tar.add(source, arcname=os.path.basename(source))


def _untar(archive, destination):
    logger = get_logger()
    logger.debug('Extracting tgz {0} to {1}...'.format(archive, destination))
    with closing(tarfile.open(name=archive)) as tar:
        tar.extractall(path=destination, members=tar.getmembers())


def _assert_profiles_exist():
    profiles = os.listdir(utils.PROFILES_DIR)
    if not profiles:
        raise CloudifyCliError(
            'No profiles to export.')


def _assert_profiles_archive(archive_path):
    with closing(tarfile.open(name=archive_path)) as tar:
        if not tar.getmembers()[0].name == 'profiles':
            raise CloudifyCliError(
                'The archive provided does not seem to be a valid '
                'Cloudify profiles archive.')


def _assert_is_tarfile(archive_path):
    if not tarfile.is_tarfile(archive_path):
        raise CloudifyCliError(
            'The archive provided must be a tar.gz archive.')


# TODO: add `cfy profiles init`
# TODO: add `cfy profiles configure` to attach key, user, etc to a profile
