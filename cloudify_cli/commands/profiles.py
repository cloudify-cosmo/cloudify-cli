import os
import shutil
import tarfile

from contextlib import closing

from cloudify.utils import get_kerberos_indication
from cloudify.cluster_status import CloudifyNodeType
from cloudify_rest_client.exceptions import (CloudifyClientError,
                                             UserUnauthorizedError)

from cloudify_cli import constants, env, utils
from cloudify_cli.cli import cfy, helptexts
from cloudify_cli.env import get_rest_client
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.table import print_data, print_single
from cloudify_cli.commands import init
from cloudify_cli.commands.cluster import (
    _all_in_one_manager,
    update_profile_logic as update_cluster_profile)


EXPORTED_KEYS_DIRNAME = '.exported-ssh-keys'
PROFILE_COLUMNS = ['name', 'manager_ip', 'manager_username', 'manager_tenant',
                   'ssh_user', 'ssh_key', 'ssh_port', 'kerberos_env',
                   'rest_port', 'rest_protocol', 'rest_certificate']
CLUSTER_PROFILE_COLUMNS = PROFILE_COLUMNS[:1] + ['hostname', 'host_ip'] \
    + PROFILE_COLUMNS[2:]


def _exported_ssh_keys_dir():
    return os.path.join(env.PROFILES_DIR, EXPORTED_KEYS_DIRNAME)


@cfy.group(name='profiles')
@cfy.options.common_options
def profiles():
    """Handle Cloudify CLI profiles

    Each profile can manage a single Cloudify manager.

    A profile is automatically created when using the `cfy profiles use`
    command.

    Profiles are named according to the IP of the manager they manage.
    """
    if not env.is_initialized():
        init.init_local_profile()


def _format_cluster_profile(profile):
    """
    Format the list of cluster nodes for display in `cfy cluster show`,
    we show the profile details of every stored cluster node.
    """
    common_attributes = {k: profile.get(k) for k in CLUSTER_PROFILE_COLUMNS}
    nodes = []
    for node in profile['cluster'][CloudifyNodeType.MANAGER]:
        # merge the common attrs with node data, but rename node's name
        # attribute to cluster_node, because the attribute 'name' is
        # reserved for the profile name
        node_data = dict(node)
        node_data['hostname'] = node_data.pop('hostname')
        nodes.append(dict(common_attributes, **node_data))
    return nodes


@profiles.command(name='show-current',
                  short_help='Retrieve current profile information')
@cfy.options.common_options
@cfy.pass_logger
@cfy.options.extended_view
def show(logger):
    """
    Shows your current active profile and it's properties
    """
    active_profile_name = env.get_active_profile()
    if active_profile_name == 'local':
        logger.info("You're currently working in local mode. "
                    "To use a manager run `cfy profiles use MANAGER_IP`")
        return

    active_profile = _get_profile(env.get_active_profile())
    if active_profile.get('cluster'):

        print_data(CLUSTER_PROFILE_COLUMNS,
                   _format_cluster_profile(active_profile),
                   'Cluster nodes in profile {0}:'
                   .format(active_profile['name']),
                   labels={
                       'profile_name': 'Name',
                       'hostname': 'Manager hostname',
                       'host_ip': 'Manager ip'})
    else:
        print_single(PROFILE_COLUMNS, active_profile, 'Active profile:')


@profiles.command(name='list',
                  short_help='List profiles')
@cfy.options.common_options
@cfy.pass_logger
@cfy.options.extended_view
def profiles_list(logger):
    """
    List all profiles
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
@cfy.options.manager_token
@cfy.options.manager_username
@cfy.options.manager_password
@cfy.options.manager_tenant()
@cfy.options.rest_port
@cfy.options.ssl_rest
@cfy.options.rest_certificate
@cfy.options.kerberos_env
@cfy.options.skip_credentials_validation
@cfy.options.common_options
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
    def _auth_args_present(kwargs):
        return any(
            kwargs.get(kwarg)
            for kwarg in ['manager_username', 'manager_password',
                          'manager_token', 'kerberos_env']
        )

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
        kwargs.setdefault('manager_tenant', 'default_tenant')
        if _auth_args_present(kwargs):
            env.check_configured_auth(
                credentials=(kwargs['manager_username'],
                             kwargs['manager_password']),
                token=kwargs['manager_token'],
                kerberos_env=kwargs['kerberos_env'],
            )
        _create_profile(
            manager_ip=manager_ip,
            profile_name=profile_name,
            skip_credentials_validation=skip_credentials_validation,
            logger=logger,
            **kwargs)
    if (
        # We test with the env here in case of switching to an existing one
        _auth_args_present(env.profile.to_dict())
        and not skip_credentials_validation
    ):
        _update_cluster_profile_to_dict(logger)


def _update_cluster_profile_to_dict(logger):
    if isinstance(env.profile.cluster, list):   # noqa
        env.profile.cluster = dict()
        env.profile.save()
    client = get_rest_client()
    if not _all_in_one_manager(client):
        update_cluster_profile(client, logger)


def _switch_profile(manager_ip, profile_name, logger, **kwargs):
    # if using an existing profile, it is an error to provide any --option,
    # because the way to update an existing profile is `cfy profiles set`
    if kwargs.get('manager_tenant') == env.profile.manager_tenant:
        del kwargs['manager_tenant']
    provided_options = [key for key, value in kwargs.items() if value]

    if any(provided_options):
        logger.warning('Profile %s already exists. '
                       'The passed in options are ignored: %s. '
                       'To update the profile, use `cfy profiles set`',
                       profile_name, ', '.join(provided_options))

    env.set_active_profile(profile_name)
    logger.info('Using manager %s', profile_name)


def _create_profile(
        manager_ip,
        profile_name,
        ssh_user,
        ssh_key,
        ssh_port,
        manager_username,
        manager_password,
        manager_tenant,
        manager_token,
        rest_port,
        ssl,
        rest_certificate,
        kerberos_env,
        skip_credentials_validation,
        logger):
    # If REST certificate is provided, then automatically
    # assume SSL.
    if rest_certificate:
        ssl = True
    rest_protocol, default_rest_port = _get_ssl_protocol_and_port(ssl)
    if not rest_port:
        rest_port = default_rest_port

    # kerberos_env default is `False` and not `None`
    kerberos_env = get_kerberos_indication(kerberos_env) or False

    logger.info('Attempting to connect to %s through port %s, using %s '
                '(SSL mode: %s)...', manager_ip, rest_port, rest_protocol, ssl)

    logger.info('Using manager %s with port %s', manager_ip, rest_port)
    _set_profile_context(
        profile_name,
        manager_ip,
        ssh_key,
        ssh_user,
        ssh_port,
        manager_username,
        manager_password,
        manager_token,
        manager_tenant,
        rest_port,
        rest_protocol,
        rest_certificate,
        kerberos_env,
        skip_credentials_validation,
    )
    env.set_active_profile(profile_name)


@profiles.command(name='delete',
                  short_help='Delete a profile')
@cfy.argument('profile-name')
@cfy.options.common_options
@cfy.pass_logger
def delete(profile_name, logger):
    """Delete a profile

    `PROFILE_NAME` is the IP of the manager the profile manages.
    """
    logger.info('Deleting profile %s...', profile_name)
    if not env.is_profile_exists(profile_name):
        raise CloudifyCliError('Profile {0} does not exist'
                               .format(profile_name))
    env.delete_profile(profile_name)
    logger.info('Profile deleted')


def _set_profile_ssl(ssl, rest_port, logger):
    if ssl is None:
        raise CloudifyCliError('Internal error: SSL must be either `on` or '
                               '`off`')

    protocol, port = _get_ssl_protocol_and_port(ssl)
    if rest_port is not None:
        port = rest_port
    if protocol == constants.SECURED_REST_PROTOCOL:
        logger.info('Enabling SSL in the local profile')
    else:
        logger.info('Disabling SSL in the local profile')

    env.profile.rest_port = port
    env.profile.rest_protocol = protocol

    manager_cluster = env.profile.cluster.get(CloudifyNodeType.MANAGER)
    if manager_cluster:
        missing_certs = []
        for node in manager_cluster:
            node['rest_port'] = port
            node['rest_protocol'] = protocol
            logger.info('Enabling SSL for %(host_ip)s', node)
            if not node.get('cert'):
                missing_certs.append(node['hostname'])
        if missing_certs:
            logger.warning('The following cluster nodes have no certificate '
                           'set: %s', ', '.join(missing_certs))
            logger.warning('If required, set the certificates for those '
                           'nodes using `cfy profiles set-cluster`')


@profiles.command(
    name='set',
    short_help='Set name/manager username/password/tenant in current profile')
@cfy.options.profile_name
@cfy.options.profile_manager_ip
@cfy.options.manager_token
@cfy.options.manager_username
@cfy.options.manager_password
@cfy.options.manager_tenant()
@cfy.options.ssh_user
@cfy.options.ssh_key
@cfy.options.ssh_port
@cfy.options.ssl_state
@cfy.options.rest_certificate
@cfy.options.rest_port
@cfy.options.kerberos_env
@cfy.options.skip_credentials_validation
@cfy.options.common_options
@cfy.pass_logger
def set_cmd(profile_name,
            manager_ip,
            manager_token,
            manager_username,
            manager_password,
            manager_tenant,
            ssh_user,
            ssh_key,
            ssh_port,
            ssl,
            rest_certificate,
            rest_port,
            kerberos_env,
            skip_credentials_validation,
            logger):
    """Set the profile name, manager username and/or password and/or tenant
    and/or ssl state (on/off) in the *current* profile
    """
    if not any([profile_name, manager_ip, ssh_user, ssh_key, ssh_port,
                manager_token, manager_username, manager_password,
                manager_tenant, ssl is not None, rest_certificate,
                kerberos_env is not None]):
        raise CloudifyCliError(
            "You must supply at least one of the following:  "
            "profile name, username, password, token, tenant, "
            "ssl, rest certificate, ssh user, ssh key, ssh port, kerberos env")
    old_name = None
    if profile_name:
        if profile_name == 'local':
            raise CloudifyCliError('Cannot use the reserved name "local"')
        if env.is_profile_exists(profile_name):
            raise CloudifyCliError('Profile {0} already exists'
                                   .format(profile_name))
        old_name = env.profile.profile_name
        env.profile.profile_name = profile_name
    if manager_ip:
        env.profile.manager_ip = manager_ip
        logger.info('Setting the manager address to `%s`', manager_ip)
    if manager_username:
        logger.info('Setting username to `%s`', manager_username)
        env.profile.manager_username = manager_username
        logger.info('Clearing non-credentials auth')
        env.profile.manager_token = None
        env.profile.kerberos_env = None
    if manager_password:
        logger.info('Setting password')
        env.profile.manager_password = manager_password
    if manager_token:
        logger.info('Setting token')
        logger.info('Clearing non-token auth')
        env.profile.manager_token = manager_token
        env.profile.manager_username = None
        env.profile.manager_password = None
        env.profile.kerberos_env = None
    if manager_tenant:
        logger.info('Setting tenant to `%s`', manager_tenant)
        env.profile.manager_tenant = manager_tenant
    if rest_certificate:
        logger.info('Setting rest certificate to `%s`', rest_certificate)
        env.profile.rest_certificate = rest_certificate
    if rest_port:
        logger.info('Setting rest port to `%s', rest_port)
        env.profile.rest_port = rest_port
    if ssh_user:
        logger.info('Setting ssh user to `%s`', ssh_user)
        env.profile.ssh_user = ssh_user
    if ssh_key:
        logger.info('Setting ssh key to `%s`', ssh_key)
        env.profile.ssh_key = ssh_key
    if ssh_port:
        logger.info('Setting ssh port to `%s`', ssh_port)
        env.profile.ssh_port = ssh_port
    if kerberos_env is not None:
        logger.info('Setting kerberos_env to `%s`', kerberos_env)
        logger.info('Clearing non-kerberos auth')
        env.profile.kerberos_env = kerberos_env
        env.profile.manager_username = None
        env.profile.manager_password = None
        env.profile.manager_token = None
    if ssl is not None:
        _set_profile_ssl(ssl, rest_port, logger)

    if not skip_credentials_validation:
        _validate_credentials(env.profile)

    env.profile.save()
    if old_name is not None:
        env.set_active_profile(profile_name)
        env.delete_profile(old_name)
    logger.info('Settings saved successfully')
    if not skip_credentials_validation:
        _update_cluster_profile_to_dict(logger)


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
    """Set connection options for a Manager cluster node.

    `CLUSTER_NODE_NAME` is the Manager cluster node name to set options for.
    """
    manager_cluster = env.profile.cluster.get(CloudifyNodeType.MANAGER)
    if not manager_cluster:
        err = CloudifyCliError('The current profile is not a cluster profile!')
        err.possible_solutions = [
            "Select a different profile using `cfy profiles use`",
            "Run `cfy cluster update-profile`"
        ]
        raise err

    changed_node = None
    for node in manager_cluster:
        if node['hostname'] == cluster_node_name:
            changed_node = node
            break
    else:
        raise CloudifyCliError(
            'Node {0} not found in the cluster'.format(cluster_node_name))

    for source, target, label in [
        (ssh_user, 'ssh_user', 'ssh user'),
        (ssh_key, 'ssh_key', 'ssh key'),
        (ssh_port, 'ssh_port', 'ssh port'),
    ]:
        if source:
            changed_node[target] = source
            logger.info('Node %s: setting %s to `%s`',
                        cluster_node_name, label, source)
    if rest_certificate:
        changed_node['cert'] = rest_certificate
        changed_node['trust_all'] = False
        changed_node['rest_protocol'] = 'https'
        logger.info('Node %s: setting rest-certificate to `%s` and enabling '
                    'certificate verification', cluster_node_name, source)
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
@cfy.options.kerberos_env_flag
@cfy.options.skip_credentials_validation
@cfy.options.common_options
@cfy.pass_logger
def unset(manager_username,
          manager_password,
          manager_tenant,
          ssh_user,
          ssh_key,
          rest_certificate,
          kerberos_env,
          skip_credentials_validation,
          logger):
    """Clear the manager username and/or password and/or tenant
    from the *current* profile
    """
    if not any([manager_username, manager_password, manager_tenant,
                rest_certificate, ssh_user, ssh_key, kerberos_env]):
        raise CloudifyCliError("You must choose at least one of the following:"
                               " username, password, tenant, kerberos_env, "
                               "rest certificate, ssh user, ssh key")
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
    if kerberos_env:
        logger.info('Clearing kerberos_env')
        env.profile.kerberos_env = None

    if not skip_credentials_validation:
        _validate_credentials(env.profile)

    env.profile.save()
    logger.info('Settings saved successfully')


@profiles.command(name='export',
                  short_help='Export all profiles to an archive')
@cfy.options.include_keys(helptexts.EXPORT_SSH_KEYS)
@cfy.options.optional_output_path
@cfy.options.common_options
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
    logger.info('Exporting profiles to %s...', destination)
    if include_keys:
        for profile in env.get_profile_names():
            _backup_ssh_key(profile)
    utils.tar(env.PROFILES_DIR, destination)
    if include_keys:
        shutil.rmtree(_exported_ssh_keys_dir())
    logger.info('Export complete!')
    logger.info(
        'You can import the profiles by running '
        '`cfy profiles import PROFILES_ARCHIVE`')


@profiles.command(name='import',
                  short_help='Import profiles from an archive')
@cfy.argument('archive-path')
@cfy.options.include_keys(helptexts.IMPORT_SSH_KEYS)
@cfy.options.common_options
@cfy.pass_logger
def import_profiles(archive_path, include_keys, logger):
    """Import profiles from a profiles archive

    WARNING: If a profile exists both in the archive and locally
    it will be overwritten (any other profiles will be left intact).

    `ARCHIVE_PATH` is the path to the profiles archive to import.
    """
    _assert_is_tarfile(archive_path)
    _assert_profiles_archive(archive_path)

    logger.info('Importing profiles from %s...', archive_path)
    utils.untar(archive_path, os.path.dirname(env.PROFILES_DIR))

    if include_keys:
        for profile in env.get_profile_names():
            _restore_ssh_key(profile)
    else:
        if EXPORTED_KEYS_DIRNAME in os.listdir(env.PROFILES_DIR):
            logger.info("The profiles archive you provided contains ssh keys "
                        "for one or more profiles. To restore those keys to "
                        "their original locations, you can use the "
                        "`--include-keys flag or copy them manually from %s ",
                        _exported_ssh_keys_dir())
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
            _exported_ssh_keys_dir(), os.path.basename(key_filepath)) + \
            '.{0}.profile'.format(profile)
        if is_backup:
            if not os.path.isdir(_exported_ssh_keys_dir()):
                os.makedirs(_exported_ssh_keys_dir(), mode=0o700)
            logger.info('Copying ssh key %s to %s...',
                        key_filepath, backup_path)
            shutil.copy2(key_filepath, backup_path)
        else:
            if os.path.isfile(backup_path):
                logger.info('Restoring ssh key for profile %s to %s...',
                            profile, key_filepath)
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
    except UserUnauthorizedError as e:
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
            "Can't use manager {0}. {1}".format(profile_name, ex))


def _get_provider_context(profile, skip_credentials_validation):
    try:
        client = _get_client_and_assert_manager(profile=profile)
    except CloudifyCliError:
        if skip_credentials_validation:
            return None
        raise

    try:
        response = client.manager.get_context()
        return response['context']
    except CloudifyClientError:
        return None


def _get_client_and_assert_manager(profile):
    if not profile.manager_ip:
        raise CloudifyCliError('No manager IP defined for Cloudify CLI '
                               'usage.\nPlease define a profile using '
                               '`cfy profiles use`')
    client = env.get_rest_client(client_profile=profile)
    _assert_manager_available(client, profile.name)
    return client


def _set_profile_context(profile_name,
                         manager_ip,
                         ssh_key,
                         ssh_user,
                         ssh_port,
                         manager_username,
                         manager_password,
                         manager_token,
                         manager_tenant,
                         rest_port,
                         rest_protocol,
                         rest_certificate,
                         kerberos_env,
                         skip_credentials_validation):
    profile = env.ProfileContext()
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
    if manager_token:
        profile.manager_token = manager_token
    if manager_tenant:
        profile.manager_tenant = manager_tenant
    profile.ssh_port = ssh_port or constants.REMOTE_EXECUTION_PORT
    profile.rest_protocol = rest_protocol
    profile.rest_certificate = rest_certificate
    profile.kerberos_env = kerberos_env

    profile.provider_context = _get_provider_context(
        profile, skip_credentials_validation)
    # We initialise the profile here so that the profile dir doesn't get
    # created if we unexpectedly fail to get the provider context
    init.init_manager_profile(profile_name=profile_name, profile=profile)


def _is_manager_secured(response_history):
    """ Checks if the manager is secured (ssl enabled)

    The manager is secured if the request was redirected to https
    """

    if response_history:
        first_response = response_history[0]
        return first_response.is_redirect \
            and first_response.headers['location'].startswith('https')

    return False


def _get_ssl_protocol_and_port(ssl):
    if ssl is not None:
        protocol, port = (constants.SECURED_REST_PROTOCOL,
                          constants.SECURED_REST_PORT) if ssl else \
            (constants.DEFAULT_REST_PROTOCOL, constants.DEFAULT_REST_PORT)
    else:
        protocol, port = None, None
    return protocol, port


@cfy.pass_logger
def _validate_credentials(profile, logger):
    logger.info('Validating credentials...')
    _get_client_and_assert_manager(profile=profile)
    logger.info('Credentials validated')
