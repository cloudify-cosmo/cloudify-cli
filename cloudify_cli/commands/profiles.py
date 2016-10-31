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

import os
import shutil
import tarfile
from contextlib import closing

from .. import env
from .. import table
from .. import utils
from ..cli import cfy
from ..cli import helptexts
from ..exceptions import CloudifyCliError

EXPORTED_KEYS_DIRNAME = '.exported-ssh-keys'
EXPORTED_SSH_KEYS_DIR = os.path.join(env.PROFILES_DIR, EXPORTED_KEYS_DIRNAME)


@cfy.group(name='profiles')
@cfy.options.verbose()
def profiles():
    """Handle Cloudify CLI profiles

    Each profile can manage a single Cloudify manager.

    A profile is automatically created when using the `cfy use`,
    and `cfy bootstrap` commands.

    Profiles are named according to the IP of the manager they manage.
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@profiles.command(name='get-active',
                  short_help='Retrieve profile information')
@cfy.options.verbose()
@cfy.pass_logger
def get(logger):
    """Gets your current active profile
    """
    active_profile_name = env.get_active_profile()
    if active_profile_name == 'local':
        logger.info("You're currently working in local mode. "
                    "To use a manager run `cfy use MANAGER_IP`"
                    " or bootstrap one")
        return

    active_profile = _get_profile(env.get_active_profile())
    _print_profiles([active_profile], 'Active profile:')


@profiles.command(name='list',
                  short_help='List profiles')
@cfy.options.verbose()
@cfy.pass_logger
def list(logger):
    """List all profiles
    """
    current_profile = env.get_active_profile()

    profiles = []
    profile_names = _get_profile_names()
    for profile in profile_names:
        profile_data = _get_profile(profile)
        if profile == current_profile:
            # Show the currently active profile by appending *
            profile_data['manager_ip'] = '*' + profile_data['manager_ip']
        profiles.append(profile_data)

    if profiles:
        logger.info('Listing all profiles...')
        _print_profiles(profiles, 'Profiles:')

    if not profile_names:
        logger.info(
            'No profiles found. You can create a new profile '
            'by bootstrapping a manager via `cfy bootstrap` or using an '
            'existing manager via the `cfy use` command')


@profiles.command(name='purge-incomplete',
                  short_help='Purge profiles in incomplete bootstrap state')
@cfy.options.verbose()
@cfy.pass_logger
def purge_incomplete(logger):
    """Purge all profiles for which the bootstrap state is incomplete
    """
    logger.info('Purging incomplete bootstrap profiles...')
    profile_names = _get_profile_names()
    for profile in profile_names:
        context = env.get_profile_context(profile)
        if context.bootstrap_state == 'Incomplete':
            logger.debug('Deleteing profiles {0}...'.format(profile))
            env.delete_profile(profile)
    logger.info('Purge complete')


@profiles.command(name='delete',
                  short_help='Delete a profile')
@cfy.argument('profile-name')
@cfy.options.verbose()
@cfy.pass_logger
def delete(profile_name, logger):
    """Delete a profile

    `PROFILE_NAME` is the IP of the manager the profile manages.
    """
    logger.info('Deleting profile {0}...'.format(profile_name))
    try:
        env.delete_profile(profile_name)
        logger.info('Profile deleted')
    except CloudifyCliError as ex:
        logger.info(str(ex))


@profiles.command(name='set-username',
                  short_help='Set manager username in profile')
@cfy.argument('username')
@cfy.options.verbose()
@cfy.pass_logger
def set_username(username, logger):
    """Set the manager username in the *current* profile

    `USERNAME` is the username of the manager user
    """
    if not username:
        raise CloudifyCliError("Can't pass an empty username. "
                               "Use the `cfy profiles unset-username` command "
                               "for that")
    env.profile.manager_username = username
    env.profile.save()
    logger.info('Manager username set to `{0}`'.format(username))


@profiles.command(name='set-password',
                  short_help='Set manager password in profile')
@cfy.argument('password')
@cfy.options.verbose()
@cfy.pass_logger
def set_password(password, logger):
    """Set the manager password in the *current* profile

    `PASSWORD` is the password of the manager user
    """
    if not password:
        raise CloudifyCliError("Can't pass an empty password. "
                               "Use the `cfy profiles unset-password` command "
                               "for that")
    env.profile.manager_password = password
    env.profile.save()
    logger.info('Manager password set')


@profiles.command(name='set-tenant',
                  short_help='Set manager tenant in profile')
@cfy.argument('tenant-name')
@cfy.options.verbose()
@cfy.pass_logger
def set_tenant(tenant_name, logger):
    """Set the manager tenant in the *current* profile

    `TENANT_NAME` is the name of the manager tenant
    """
    if not tenant_name:
        raise CloudifyCliError("Can't pass an empty tenant name. "
                               "Use the `cfy profiles unset-tenant` command "
                               "for that")
    env.profile.manager_tenant = tenant_name
    env.profile.save()
    logger.info('Manager tenant set to `{0}`'.format(tenant_name))


@profiles.command(name='unset-username',
                  short_help='Clear manager username from profile')
@cfy.options.verbose()
@cfy.pass_logger
def unset_username(logger):
    """Clear the manager username from the *current* profile
    """
    env.profile.manager_username = None
    env.profile.save()
    logger.info('Manager username was cleared')


@profiles.command(name='unset-password',
                  short_help='Clear manager password from profile')
@cfy.options.verbose()
@cfy.pass_logger
def unset_password(logger):
    """Clear the manager password from the *current* profile
    """
    env.profile.manager_password = None
    env.profile.save()
    logger.info('Manager password was cleared')


@profiles.command(name='unset-tenant',
                  short_help='Clear manager tenant from profile')
@cfy.options.verbose()
@cfy.pass_logger
def unset_tenant(logger):
    """Clear the manager tenant from the *current* profile
    """
    env.profile.manager_tenant = None
    env.profile.save()
    logger.info('Manager tenant was cleared')


@profiles.command(name='export',
                  short_help='Export all profiles to an archive')
@cfy.options.include_keys(helptexts.EXPORT_SSH_KEYS)
@cfy.options.optional_output_path
@cfy.options.verbose()
@cfy.pass_logger
def export_profiles(include_keys, output_path, logger):
    """Export all profiles to a file

    WARNING: Including the ssh keys of your profiles in the archive means
    that once the profiles are imported, the ssh keys will be put back
    in their original locations!

    If `-o / --output-path` is omitted, the archive's name will be
    `cfy-profiles.tar.gz`.
    """
    _assert_profiles_exist()

    destination = output_path or \
        os.path.join(os.getcwd(), 'cfy-profiles.tar.gz')

    # TODO: Copy exported ssh keys to each profile's directory
    logger.info('Exporting profiles to {0}...'.format(destination))
    if include_keys:
        for profile in _get_profile_names():
            _backup_ssh_key(profile)
    utils.tar(env.PROFILES_DIR, destination)
    if include_keys:
        shutil.rmtree(EXPORTED_SSH_KEYS_DIR)
    logger.info('Export complete!')
    logger.info(
        'You can import the profiles by running '
        '`cfy profiles import PROFILES_ARCHIVE`')


@profiles.command(name='import',
                  short_help='Import profiles from an archive')
@cfy.argument('archive-path')
@cfy.options.include_keys(helptexts.IMPORT_SSH_KEYS)
@cfy.options.verbose()
@cfy.pass_logger
def import_profiles(archive_path, include_keys, logger):
    """Import profiles from a profiles archive

    WARNING: If a profile exists both in the archive and locally
    it will be overwritten (any other profiles will be left intact).

    `ARCHIVE_PATH` is the path to the profiles archive to import.
    """
    _assert_is_tarfile(archive_path)
    _assert_profiles_archive(archive_path)

    logger.info('Importing profiles from {0}...'.format(archive_path))
    utils.untar(archive_path, os.path.dirname(env.PROFILES_DIR))

    if include_keys:
        for profile in _get_profile_names():
            _restore_ssh_key(profile)
    else:
        if EXPORTED_KEYS_DIRNAME in os.listdir(env.PROFILES_DIR):
            logger.info("The profiles archive you provided contains ssh keys "
                        "for one or more profiles. To restore those keys to "
                        "their original locations, you can use the "
                        "`--include-keys flag or copy them manually from {0} "
                        .format(EXPORTED_SSH_KEYS_DIR))
    logger.info('Import complete!')
    logger.info('You can list profiles using `cfy profiles list`')


def _assert_profiles_exist():
    if not _get_profile_names():
        raise CloudifyCliError('No profiles to export')


def _assert_profiles_archive(archive_path):
    with closing(tarfile.open(name=archive_path)) as tar:
        if not tar.getmembers()[0].name == 'profiles':
            raise CloudifyCliError(
                'The archive provided does not seem to be a valid '
                'Cloudify profiles archive')


def _assert_is_tarfile(archive_path):
    if not tarfile.is_tarfile(archive_path):
        raise CloudifyCliError('The archive provided must be a tar.gz archive')


def _get_profile_names():
    # TODO: This is too.. ambiguous. We should change it so there are
    # no exclusions.
    excluded = ['local', EXPORTED_KEYS_DIRNAME]
    profile_names = [item for item in os.listdir(env.PROFILES_DIR)
                     if item not in excluded]

    return profile_names


def _backup_ssh_key(profile):
    return _move_ssh_key(profile, is_backup=True)


def _restore_ssh_key(profile):
    return _move_ssh_key(profile, is_backup=False)


@cfy.pass_logger
def _move_ssh_key(profile, logger, is_backup):
    """Iterate through all profiles and move their ssh keys

    This is how we backup and restore ssh keys.
    """
    context = env.get_profile_context(profile)
    key_filepath = context.ssh_key
    if key_filepath:
        backup_path = os.path.join(
            EXPORTED_SSH_KEYS_DIR, os.path.basename(key_filepath)) + \
            '.{0}.profile'.format(profile)
        if is_backup:
            if not os.path.isdir(EXPORTED_SSH_KEYS_DIR):
                os.makedirs(EXPORTED_SSH_KEYS_DIR)
            logger.info('Copying ssh key {0} to {1}...'.format(
                key_filepath, backup_path))
            shutil.copy2(key_filepath, backup_path)
        else:
            if os.path.isfile(backup_path):
                logger.info(
                    'Restoring ssh key for profile {0} to {1}...'.format(
                        profile, key_filepath))
                shutil.move(backup_path, key_filepath)


def _get_profile(profile_name):
    current_profile = env.get_active_profile()
    env.set_active_profile(profile_name)
    context = env.get_profile_context(profile_name)
    env.set_active_profile(current_profile)

    return context.to_dict()


def _print_profiles(profiles, header):
    columns = [
            'manager_ip',
            'ssh_user',
            'ssh_key_path',
            'ssh_port',
            'rest_port',
            'rest_protocol',
            'manager_username',
            'manager_tenant',
            'bootstrap_state'
        ]
    pt = table.generate(columns, data=profiles)
    table.log(header, pt)
