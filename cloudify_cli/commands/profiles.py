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

from cloudify_rest_client.exceptions import CloudifyClientError, \
    UserUnauthorizedError

from . import init
from .. import env
from ..table import print_data
from .. import utils
from ..cli import cfy
from .. import constants
from ..cli import helptexts
from ..exceptions import CloudifyCliError

EXPORTED_KEYS_DIRNAME = '.exported-ssh-keys'
EXPORTED_SSH_KEYS_DIR = os.path.join(env.PROFILES_DIR, EXPORTED_KEYS_DIRNAME)
PROFILE_COLUMNS = ['name', 'manager_ip', 'manager_username', 'manager_tenant',
                   'ssh_user', 'ssh_key_path', 'ssh_port',
                   'rest_port', 'rest_protocol', 'rest_certificate']


@cfy.group(name='profiles')
@cfy.options.verbose()
def profiles():
    """Handle Cloudify CLI profiles

    Each profile can manage a single Cloudify manager.

    A profile is automatically created when using the `cfy profiles use`
    command.

    Profiles are named according to the IP of the manager they manage.
    """
    if not env.is_initialized():
        init.init_local_profile()


@profiles.command(name='show-current',
                  short_help='Retrieve current profile information')
@cfy.options.verbose()
@cfy.pass_logger
def show(logger):
    """Shows your current active profile and it's properties
    """
    active_profile_name = env.get_active_profile()
    if active_profile_name == 'local':
        logger.info("You're currently working in local mode. "
                    "To use a manager run `cfy profiles use MANAGER_IP`")
        return

    active_profile = _get_profile(env.get_active_profile())
    print_data(PROFILE_COLUMNS, active_profile, 'Active profile:')


@profiles.command(name='list',
                  short_help='List profiles')
@cfy.options.verbose()
@cfy.pass_logger
def list(logger):
    """List all profiles
    """
    current_profile = env.get_active_profile()

    profiles = []
    profile_names = env.get_profile_names()
    for profile in profile_names:
        profile_data = _get_profile(profile)
        if profile == current_profile:
            # Show the currently active profile by appending *
            profile_data['name'] = '*' + profile_data['name']
        profiles.append(profile_data)

    if profiles:
        logger.info('Listing all profiles...')
        print_data(PROFILE_COLUMNS, profiles, 'Profiles:')

    if not profile_names:
        logger.info(
            'No profiles found. You can create a new profile '
            'by using an existing manager via the `cfy profiles use` command')


@profiles.command(name='use',
                  short_help='Control a specific manager')
@cfy.argument('manager-ip')
@cfy.options.profile_name
@cfy.options.ssh_user
@cfy.options.ssh_key
@cfy.options.ssh_port
@cfy.options.manager_username
@cfy.options.manager_password
@cfy.options.manager_tenant
@cfy.options.rest_port
@cfy.options.ssl_rest
@cfy.options.rest_certificate
@cfy.options.skip_credentials_validation
@cfy.options.verbose()
@cfy.pass_logger
def use(manager_ip,
        profile_name,
        skip_credentials_validation,
        logger,
        **kwargs):
    """Control a specific manager

    `PROFILE_NAME` can be either a manager IP or `local`.

    Additional CLI commands will be added after a manager is used.
    To stop using a manager, you can run `cfy init -r`.
    """
    if not profile_name:
        profile_name = manager_ip
    if profile_name == 'local':
        logger.info('Using local environment...')
        if not env.is_profile_exists(profile_name):
            init.init_local_profile()
        env.set_active_profile('local')
        return

    if env.is_profile_exists(profile_name):
        _switch_profile(
            manager_ip=manager_ip,
            profile_name=profile_name,
            logger=logger,
            **kwargs)
    else:
        _create_profile(
            manager_ip=manager_ip,
            profile_name=profile_name,
            skip_credentials_validation=skip_credentials_validation,
            logger=logger,
            **kwargs)


def _switch_profile(manager_ip, profile_name, logger, **kwargs):
    # if using an existing profile, it is an error to provide any --option,
    # because the way to update an existing profile is `cfy profiles set`
    provided_options = [key for key, value in kwargs.items() if value]
    if any(provided_options):
        logger.warning('Profile {0} already exists. '
                       'The passed in options are ignored: {1}. '
                       'To update the profile, use `cfy profiles set`'
                       .format(profile_name, ', '.join(provided_options)))

    env.set_active_profile(profile_name)
    logger.info('Using manager {0}'.format(profile_name))


def _create_profile(
        manager_ip,
        profile_name,
        ssh_user,
        ssh_key,
        ssh_port,
        manager_username,
        manager_password,
        manager_tenant,
        rest_port,
        ssl,
        rest_certificate,
        skip_credentials_validation,
        logger):
    # If REST certificate is provided, then automatically
    # assume SSL.
    if rest_certificate:
        ssl = True

    rest_protocol = constants.SECURED_REST_PROTOCOL if ssl else \
        constants.DEFAULT_REST_PROTOCOL

    if not rest_port:
        rest_port = constants.SECURED_REST_PORT if ssl else \
            constants.DEFAULT_REST_PORT

    logger.info('Attempting to connect to {0} through port {1}, using {2} '
                '(SSL mode: {3})...'.format(manager_ip, rest_port,
                                            rest_protocol, ssl))

    # First, attempt to get the provider from the manager - should it fail,
    # the manager's profile directory won't be created
    provider_context = _get_provider_context(
        profile_name,
        manager_ip,
        rest_port,
        rest_protocol,
        rest_certificate,
        manager_username,
        manager_password,
        manager_tenant,
        skip_credentials_validation
    )

    init.init_manager_profile(profile_name=profile_name)
    env.set_active_profile(profile_name)

    logger.info('Using manager {0} with port {1}'.format(
        manager_ip, rest_port))

    _set_profile_context(
        profile_name,
        provider_context,
        manager_ip,
        ssh_key,
        ssh_user,
        ssh_port,
        manager_username,
        manager_password,
        manager_tenant,
        rest_port,
        rest_protocol,
        rest_certificate
    )


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


def set_profile(profile_name,
                manager_username,
                manager_password,
                manager_tenant,
                ssh_user,
                ssh_key,
                ssh_port,
                ssl,
                rest_certificate,
                skip_credentials_validation,
                logger):
    """Set the profile name, manager username and/or password and/or tenant
    and/or ssl state (on/off) in the *current* profile
    """
    if not any([profile_name, ssh_user, ssh_key, ssh_port, manager_username,
                manager_password, manager_tenant, ssl, rest_certificate]):
        raise CloudifyCliError(
            "You must supply at least one of the following:  "
            "profile name, username, password, tenant, "
            "ssl, rest certificate, ssh user, ssh key, ssh port")
    username = manager_username or env.get_username()
    password = manager_password or env.get_password()
    tenant = manager_tenant or env.get_tenant_name()

    if not skip_credentials_validation:
        _validate_credentials(username, password, tenant, rest_certificate)
    old_name = None
    if profile_name:
        if profile_name == 'local':
            raise CloudifyCliError('Cannot use the reserved name "local"')
        if env.is_profile_exists(profile_name):
            raise CloudifyCliError('Profile {0} already exists'
                                   .format(profile_name))
        old_name = env.profile.profile_name
        env.profile.profile_name = profile_name
    if manager_username:
        logger.info('Setting username to `{0}`'.format(manager_username))
        env.profile.manager_username = manager_username
    if manager_password:
        logger.info('Setting password to `{0}`'.format(manager_password))
        env.profile.manager_password = manager_password
    if manager_tenant:
        logger.info('Setting tenant to `{0}`'.format(manager_tenant))
        env.profile.manager_tenant = manager_tenant
    if ssl is not None:
        _set_profile_ssl(ssl, logger)
    if rest_certificate:
        logger.info(
            'Setting rest certificate to `{0}`'.format(rest_certificate))
        env.profile.rest_certificate = rest_certificate
    if ssh_user:
        logger.info('Setting ssh user to `{0}`'.format(ssh_user))
        env.profile.ssh_user = ssh_user
    if ssh_key:
        logger.info('Setting ssh key to `{0}`'.format(ssh_key))
        env.profile.ssh_key = ssh_key
    if ssh_port:
        logger.info('Setting ssh port to `{0}`'.format(ssh_port))
        env.profile.ssh_port = ssh_port

    env.profile.save()
    if old_name is not None:
        env.set_active_profile(profile_name)
        env.delete_profile(old_name)
    logger.info('Settings saved successfully')


def _set_profile_ssl(ssl, logger):
    ssl = str(ssl).lower()
    if ssl == 'on':
        logger.info('Enabling SSL in the local profile')
        port = constants.SECURED_REST_PORT
        protocol = constants.SECURED_REST_PROTOCOL
    elif ssl == 'off':
        logger.info('Disabling SSL in the local profile')
        port = constants.DEFAULT_REST_PORT
        protocol = constants.DEFAULT_REST_PROTOCOL
    else:
        raise CloudifyCliError('SSL must be either `on` or `off`')

    env.profile.rest_port = port
    env.profile.rest_protocol = protocol

    if env.profile.cluster:
        for node in env.profile.cluster:
            node['rest_port'] = port
            node['rest_protocol'] = protocol
            node['trust_all'] = True
            logger.info('Enabling SSL for {0} without certificate validation'
                        .format(node['manager_ip']))


@profiles.command(
    name='set',
    short_help='Set name/manager username/password/tenant in current profile')
@cfy.options.profile_name
@cfy.options.manager_username
@cfy.options.manager_password
@cfy.options.manager_tenant
@cfy.options.ssh_user
@cfy.options.ssh_key
@cfy.options.ssh_port
@cfy.options.ssl_state
@cfy.options.rest_certificate
@cfy.options.skip_credentials_validation
@cfy.options.verbose()
@cfy.pass_logger
def set_cmd(profile_name,
            manager_username,
            manager_password,
            manager_tenant,
            ssh_user,
            ssh_key,
            ssh_port,
            ssl,
            rest_certificate,
            skip_credentials_validation,
            logger):
    return set_profile(profile_name,
                       manager_username,
                       manager_password,
                       manager_tenant,
                       ssh_user,
                       ssh_key,
                       ssh_port,
                       ssl,
                       rest_certificate,
                       skip_credentials_validation,
                       logger)


@profiles.command(
    name='set-cluster',
    short_help='Set connection options for a cluster node')
@cfy.argument('cluster-node-name')
@cfy.options.ssh_user
@cfy.options.ssh_key
@cfy.options.ssh_port
@cfy.options.rest_certificate
@cfy.pass_logger
def set_cluster(cluster_node_name,
                ssh_user,
                ssh_key,
                ssh_port,
                rest_certificate,
                logger):
    """Set connection options for a cluster node.

    `CLUSTER_NODE_NAME` is the name of the cluster node to set options for.
    """
    if not env.profile.cluster:
        err = CloudifyCliError('The current profile is not a cluster profile!')
        err.possible_solutions = [
            "Select a different profile using `cfy profiles use`",
            "Run `cfy cluster update-profile`"
        ]
        raise err

    changed_node = None
    for node in env.profile.cluster:
        if node['name'] == cluster_node_name:
            changed_node = node
            break
    else:
        raise CloudifyCliError(
            'Node {0} not found in the cluster'.format(cluster_node_name))

    for source, target, label in [
        (ssh_user, 'ssh_user', 'ssh user'),
        (ssh_key, 'ssh_key', 'ssh key'),
        (ssh_port, 'ssh_port', 'ssh port'),
        (rest_certificate, 'cert', 'rest certificate'),
    ]:
        if source:
            changed_node[target] = source
            logger.info('Node {0}: setting {1} to `{2}`'
                        .format(cluster_node_name, label, source))

    env.profile.save()
    logger.info('Settings saved successfully')


@profiles.command(
    name='unset',
    short_help='Clear manager username/password/tenant from current profile')
@cfy.options.manager_username_flag
@cfy.options.manager_password_flag
@cfy.options.manager_tenant_flag
@cfy.options.ssh_user_flag
@cfy.options.ssh_key_flag
@cfy.options.rest_certificate_flag
@cfy.options.skip_credentials_validation
@cfy.options.verbose()
@cfy.pass_logger
def unset(manager_username,
          manager_password,
          manager_tenant,
          ssh_user,
          ssh_key,
          rest_certificate,
          skip_credentials_validation,
          logger):
    """Clear the manager username and/or password and/or tenant
    from the *current* profile
    """
    if not any([manager_username, manager_password, manager_tenant,
                rest_certificate, ssh_user, ssh_key]):
        raise CloudifyCliError("You must choose at least one of the following:"
                               " username, password, tenant, "
                               "rest certificate, ssh user, ssh key")
    if manager_username:
        username = os.environ.get(constants.CLOUDIFY_USERNAME_ENV)
    else:
        username = env.profile.manager_username
    if manager_password:
        password = os.environ.get(constants.CLOUDIFY_PASSWORD_ENV)
    else:
        password = env.profile.manager_password
    if manager_tenant:
        tenant = os.environ.get(constants.CLOUDIFY_TENANT_ENV)
    else:
        tenant = env.profile.manager_tenant
    if rest_certificate:
        cert = os.environ.get(constants.LOCAL_REST_CERT_FILE) \
               or env.get_default_rest_cert_local_path()
    else:
        cert = None

    if not skip_credentials_validation:
        _validate_credentials(username, password, tenant, cert)

    if manager_username:
        logger.info('Clearing manager username')
        env.profile.manager_username = None
    if manager_password:
        logger.info('Clearing manager password')
        env.profile.manager_password = None
    if manager_tenant:
        logger.info('Clearing manager tenant')
        env.profile.manager_tenant = None
    if rest_certificate:
        logger.info('Clearing rest certificate')
        env.profile.rest_certificate = None
    if ssh_user:
        logger.info('Clearing ssh user')
        env.profile.ssh_user = None
    if ssh_key:
        logger.info('Clearing ssh key')
        env.profile.ssh_key = None
    env.profile.save()
    logger.info('Settings saved successfully')


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
        for profile in env.get_profile_names():
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
        for profile in env.get_profile_names():
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
    if not env.get_profile_names():
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


def _assert_manager_available(client, profile_name):
    try:
        return client.manager.get_status()
    except UserUnauthorizedError, e:
        raise CloudifyCliError(
            "Can't use manager {0}\n{1}.".format(
                profile_name,
                str(e)
            )
        )
    # The problem here is that, for instance,
    # any problem raised by the rest client will trigger this.
    # Triggering a CloudifyClientError only doesn't actually deal
    # with situations like No route to host and the likes.
    except Exception as ex:
        raise CloudifyCliError(
            "Can't use manager {0}. {1}".format(profile_name, str(ex.message)))


def _get_provider_context(profile_name,
                          manager_ip,
                          rest_port,
                          rest_protocol,
                          rest_certificate,
                          manager_username,
                          manager_password,
                          manager_tenant,
                          skip_credentials_validation):
    try:
        client = _get_client_and_assert_manager(
            profile_name,
            manager_ip,
            rest_port,
            rest_protocol,
            rest_certificate,
            manager_username,
            manager_password,
            manager_tenant
        )
    except CloudifyCliError:
        if skip_credentials_validation:
            return None
        raise

    try:
        response = client.manager.get_context()
        return response['context']
    except CloudifyClientError:
        return None


def _get_client_and_assert_manager(profile_name,
                                   manager_ip=None,
                                   rest_port=None,
                                   rest_protocol=None,
                                   rest_certificate=None,
                                   manager_username=None,
                                   manager_password=None,
                                   manager_tenant=None):
    # Attempt to update the profile with an existing profile context, if one
    # is available. This is relevant in case the user didn't pass a username
    # or a password, and was expecting them to be taken from the old profile
    env.profile = env.get_profile_context(profile_name, suppress_error=True)

    client = env.get_rest_client(
        rest_host=manager_ip,
        rest_port=rest_port,
        rest_protocol=rest_protocol,
        rest_cert=rest_certificate,
        skip_version_check=True,
        username=manager_username,
        password=manager_password,
        tenant_name=manager_tenant
    )

    _assert_manager_available(client, profile_name)
    return client


def _set_profile_context(profile_name,
                         provider_context,
                         manager_ip,
                         ssh_key,
                         ssh_user,
                         ssh_port,
                         manager_username,
                         manager_password,
                         manager_tenant,
                         rest_port,
                         rest_protocol,
                         rest_certificate):

    profile = env.get_profile_context(profile_name)
    profile.provider_context = provider_context
    if profile_name:
        profile.profile_name = profile_name
    if manager_ip:
        profile.manager_ip = manager_ip
    if ssh_key:
        profile.ssh_key = ssh_key
    if ssh_user:
        profile.ssh_user = ssh_user
    if rest_port:
        profile.rest_port = rest_port
    if manager_username:
        profile.manager_username = manager_username
    if manager_password:
        profile.manager_password = manager_password
    if manager_tenant:
        profile.manager_tenant = manager_tenant
    profile.ssh_port = ssh_port or constants.REMOTE_EXECUTION_PORT
    profile.rest_protocol = rest_protocol
    profile.rest_certificate = rest_certificate

    profile.save()


def _is_manager_secured(response_history):
    """ Checks if the manager is secured (ssl enabled)

    The manager is secured if the request was redirected to https
    """

    if response_history:
        first_response = response_history[0]
        return first_response.is_redirect \
            and first_response.headers['location'].startswith('https')

    return False


@cfy.pass_logger
def _validate_credentials(username, password, tenant, certificate, logger):
    logger.info('Validating credentials...')
    _get_client_and_assert_manager(
        profile_name=env.profile.profile_name,
        manager_username=username,
        manager_password=password,
        manager_tenant=tenant,
        rest_certificate=certificate
    )
    logger.info('Credentials validated')
