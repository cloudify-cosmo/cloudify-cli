########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import shutil
import socket
import os
import sys
import time
import urllib2
import abc
import jsonschema
from fabric import api
from fabric.context_managers import settings
from fabric.context_managers import hide
from fabric.context_managers import cd

from cloudify_rest_client import exceptions as rest_exception

from cloudify_cli import constants
from cloudify_cli import exceptions
from cloudify_cli import utils
from cloudify_cli import cli
from cloudify_cli.logger import get_logger


def update_config_at_paths(struct, paths, f):
    """ Transforms properties at given paths using the "f" function.
    Ignores non-existing paths. """

    def kern(struct, p):
        if not p:
            return
        if p[0] not in struct:
            return
        if len(p) == 1:
            struct[p[0]] = f(struct[p[0]])
            return
        kern(struct[p[0]], p[1:])

    for p in paths:
        kern(struct, p)


DISTRO_EXT = {'Ubuntu': '.deb', 'centos': '.rpm', 'xitUbuntu': '.deb'}


class BaseProviderClass(object):
    """
    This is the basic provider class supplied with the CLI.
    It can be imported by the provider's code by inheritance
    into the ProviderManager class.
    Each of the below methods can be overridden in favor of a different impl.
    """
    __metaclass__ = abc.ABCMeta

    schema = {}
    CONFIG_NAMES_TO_MODIFY = ()  # No default (empty tuple)
    CONFIG_FILES_PATHS_TO_MODIFY = ()  # No default (empty tuple)

    def __init__(self, provider_config, is_verbose_output):

        cli.set_global_verbosity_level(is_verbose_output)
        self.provider_config = provider_config
        self.is_verbose_output = is_verbose_output
        self.keep_up_on_failure = False
        self.logger = get_logger()

    @abc.abstractmethod
    def provision(self):
        """
        provisions resources for the management server
        """
        return

    @abc.abstractmethod
    def validate(self):
        """
        validations to be performed before provisioning and bootstrapping
        the management server.

        :param dict validation_errors: dict to hold all validation errors.
        :rtype: `dict` of validaiton_errors.
        """
        self.logger.debug("no resource validation methods defined!")
        return {}

    @abc.abstractmethod
    def teardown(self, provider_context, ignore_validation=False):
        """
        tears down the management server and its accompanied provisioned
        resources
        """
        return

    def bootstrap(self, public_ip, private_ip, ssh_key, ssh_user):
        """
        bootstraps Cloudify on the management server.

        :param string public_ip: public ip of the provisioned instance.
        :param string private_ip: private ip of the provisioned instance.
         (for configuration purposes).
        :param string ssh_key: path to the ssh key to be used for
         connecting to the instance.
        :param string ssh_user: the user to use when connecting to the
         instance.
        :param bool dev_mode: states whether dev_mode should be applied.
        :rtype: `bool` True if succeeded, False otherwise. If False is returned
         and 'cfy bootstrap' was executed with the keep-up-on-failure flag, the
         provisioned resources will remain. If the flag is omitted, they will
         be torn down.
        """
        ssh_config = self.provider_config['cloudify']['bootstrap']['ssh']

        def _run_with_retries(command, retries=ssh_config['command_retries'],
                              sleeper=ssh_config['retries_interval'],
                              return_output_on_success=False):
            r = None
            error_message = None
            for execution in range(retries):
                self.logger.debug('running command: {0}'.format(command))
                try:
                    if not self.is_verbose_output:
                        with hide('running', 'stdout'):
                            r = self._run_command_via_ssh(command, public_ip,
                                                          ssh_user,
                                                          ssh_key)
                    else:
                        r = self._run_command_via_ssh(command, public_ip,
                                                      ssh_user,
                                                      ssh_key)
                except BaseException as e:
                    self.logger.warning(
                        'Error occurred while running command: '
                        '{0}'
                        .format(str(e)))
                    error_message = str(e)
                if r and r.succeeded:
                    self.logger.debug('successfully ran command: {0}'
                                      .format(command))
                    return r.stdout if return_output_on_success else True
                elif r:
                    error_message = r.stderr
                self.logger.warning('retrying command: {0}'.format(command))
                time.sleep(sleeper)
            self.logger.error('failed to run: {0}, {1}'
                              .format(command, error_message))
            return False

        def _download_package(url, path, distro):
            if 'Ubuntu' in distro:
                return _run_with_retries('sudo wget {0} -P {1}'.format(
                    path, url))
            elif 'centos' in distro:
                with cd(path):
                    return _run_with_retries('sudo curl -O {0}')

        def _unpack(path, distro):
            if 'Ubuntu' in distro:
                return _run_with_retries('sudo dpkg -i {0}/*.deb'.format(path))
            elif 'centos' in distro:
                return _run_with_retries('sudo rpm -i {0}/*.rpm'.format(path))

        def check_distro_type_match(url, distro):
            self.logger.debug('checking distro-type match for url: {0}'
                              .format(url))
            ext = get_ext(url)
            if not DISTRO_EXT[distro] == ext:
                self.logger.error('wrong package type: '
                                  '{0} required. {1} supplied. in url: {2}'
                                  .format(DISTRO_EXT[distro], ext, url))
                return False
            return True

        def get_distro():
            self.logger.debug('identifying instance distribution...')
            return _run_with_retries(
                'python -c "import platform; print platform.dist()[0]"',
                return_output_on_success=True)

        def get_ext(url):
            self.logger.debug('extracting file extension from url')
            file = urllib2.unquote(url).decode('utf8').split('/')[-1]
            return os.path.splitext(file)[1]

        def _run(command):
            return _run_with_retries(command)

        self.logger.info('initializing manager on the machine at {0}'
                         .format(public_ip))
        cloudify_config = self.provider_config['cloudify']

        server_packages = cloudify_config['server']['packages']
        agent_packages = cloudify_config['agents']['packages']
        ui_included = True if 'ui_package_url' in server_packages \
            else False
        # get linux distribution to install and download
        # packages accordingly
        dist = get_distro()  # dist is either the dist name or False
        if dist:
            self.logger.debug('distribution is: {0}'.format(dist))
        else:
            self.logger.error('could not identify distribution.')
            return False

        # check package compatibility with current distro
        self.logger.debug('checking package-distro compatibility')
        for package, package_url in server_packages.items():
            if not check_distro_type_match(package_url, dist):
                raise RuntimeError('wrong package type')
        for package, package_url in agent_packages.items():
            if not check_distro_type_match(package_url, dist):
                raise RuntimeError('wrong agent package type')

        # TODO: consolidate server package downloading
        self.logger.info('downloading cloudify-components package...')
        success = _download_package(
            constants.CLOUDIFY_PACKAGES_PATH,
            server_packages['components_package_url'],
            dist)
        if not success:
            self.logger.error('failed to download components package. '
                              'please ensure package exists in its '
                              'configured location in the config file')
            return False

        self.logger.info('downloading cloudify-core package...')
        success = _download_package(
            constants.CLOUDIFY_PACKAGES_PATH,
            server_packages['core_package_url'],
            dist)
        if not success:
            self.logger.error('failed to download core package. '
                              'please ensure package exists in its '
                              'configured location in the config file')
            return False

        if ui_included:
            self.logger.info('downloading cloudify-ui...')
            success = _download_package(
                constants.CLOUDIFY_UI_PACKAGE_PATH,
                server_packages['ui_package_url'],
                dist)
            if not success:
                self.logger.error('failed to download ui package. '
                                  'please ensure package exists in its '
                                  'configured location in the config file')
                return False
        else:
            self.logger.debug('ui url not configured in provider config. '
                              'skipping ui installation.')

        for agent, agent_url in \
                agent_packages.items():
            success = _download_package(
                constants.CLOUDIFY_AGENT_PACKAGE_PATH,
                agent_packages[agent],
                dist)
            if not success:
                self.logger.error('failed to download {}. '
                                  'please ensure package exists in its '
                                  'configured location in the config file'
                                  .format(agent_url))
                return False

        self.logger.info('unpacking cloudify-core packages...')
        success = _unpack(
            constants.CLOUDIFY_PACKAGES_PATH,
            dist)
        if not success:
            self.logger.error('failed to unpack cloudify-core package.')
            return False

        self.logger.debug('verifying verbosity for installation process.')
        v = self.is_verbose_output
        self.is_verbose_output = True

        self.logger.info('installing cloudify on {0}...'.format(public_ip))
        success = _run('sudo {0}/cloudify-components-bootstrap.sh'.format(
            constants.CLOUDIFY_COMPONENTS_PACKAGE_PATH))
        if not success:
            self.logger.error('failed to install cloudify-components package.')
            return False

        # declare user to run celery. this is passed to the core package's
        # bootstrap script for installation.
        celery_user = ssh_user
        success = _run('sudo {0}/cloudify-core-bootstrap.sh {1} {2}'.format(
            constants.CLOUDIFY_CORE_PACKAGE_PATH, celery_user, private_ip))
        if not success:
            self.logger.error('failed to install cloudify-core package.')
            return False

        if ui_included:
            self.logger.info('installing cloudify-ui...')
            self.is_verbose_output = False
            success = _unpack(
                constants.CLOUDIFY_UI_PACKAGE_PATH,
                dist)
            if not success:
                self.logger.error('failed to install cloudify-ui.')
                return False
            self.logger.info('cloudify-ui installation successful.')

        self.logger.info('deploying cloudify agents')
        self.is_verbose_output = False
        success = _unpack(
            constants.CLOUDIFY_AGENT_PACKAGE_PATH,
            dist)
        if not success:
            self.logger.error('failed to install cloudify agents.')
            return False
        self.logger.info('cloudify agents installation successful.')

        self.is_verbose_output = True
        self.logger.debug('setting verbosity to previous state')
        self.is_verbose_output = v
        return True

    def ensure_connectivity_with_management_server(self, mgmt_ip, mgmt_ssh_key,
                                                   mgmt_ssh_user):
        """
        Checks for connectivity with the management server.
        This method is called right after provision(), but before bootstrap(),
        to ensure that the management server is truly reachable (e.g.
        verify sshd is up and running, etc..)

        :param string mgmt_ip: public ip of the provisioned instance.
        :param string mgmt_ssh_key: path to the ssh key to be used for
         connecting to the instance.
        :param string mgmt_ssh_user: the user to use when connecting to the
         instance.
        :return: True if successfully connected to the management server,
            False otherwise.
        """
        ssh_config = self.provider_config['cloudify']['bootstrap']['ssh']
        retries = ssh_config['initial_connectivity_retries']
        retries_interval = ssh_config['initial_connectivity_retries_interval']
        socket_timeout = ssh_config['socket_timeout']

        num_of_retries_without_log_message = 5

        for retry in range(retries):
            try:
                log_func = self.logger.info if \
                    retry >= num_of_retries_without_log_message \
                    else self.logger.debug
                log_func('Trying to open an SSH socket to management machine '
                         '(attempt {0} of {1})'.format(retry + 1, retries))

                sock = socket.create_connection((mgmt_ip, 22), socket_timeout)
                sock.close()
                break
            except (socket.timeout, socket.error) as e:
                # note: This could possibly be a '[Errno 110] Connection timed
                # out' error caused by the network stack, which has a different
                # timeout setting than the one used for the python socket.
                self.logger.debug('Error occurred in initial '
                                  'connectivity check with '
                                  'management server: {0}'
                                  .format(str(e)))
            time.sleep(retries_interval)
        else:
            self.logger.error('Failed to open an SSH socket '
                              'to management machine '
                              '(tried {0} times)'
                              .format(retries))
            return False

        test_ssh_cmd = ''
        try:
            self._run_command_via_ssh(test_ssh_cmd, mgmt_ip,
                                      mgmt_ssh_user, mgmt_ssh_key)
            return True
        except BaseException as e:
            self.logger.error('Error occurred while trying to SSH connect to '
                              'management machine: {}'.format(str(e)))
            return False

    def augment_schema_with_common(self):
        self.schema.setdefault('type', 'object')
        props = self.schema.setdefault('properties', {})
        cloudify = props.setdefault('cloudify', {})
        cloudify.setdefault('type', 'object')
        cloudify.setdefault('properties', {}).update({
            "resources_prefix": {
                "type": "string",
            },
        })

    def validate_schema(self):
        """
        this is a basic implementation of schema validation.
        uses the Draft4Validator from jsonschema to validate the provider's
        config.
        a schema file must be created and its contents supplied
        when initializing the ProviderManager class using the schema
        parameter.

        :param dict schema: a schema to compare the provider's config to.
         the provider's config is already initialized within the
         ProviderManager class in the provider's code.
        :rtype: `dict` of validation_errors.
        """
        if not self.schema:
            self.logger.warn('schema is not provided in '
                             'class "{0}", skipping schema '
                             'validation'
                             .format(self.__class__))
            return {}

        validation_errors = {}
        self.logger.debug('validating config file against provided schema...')
        try:
            v = jsonschema.Draft4Validator(self.schema)
        except AttributeError as e:
            raise jsonschema.ValidationError(
                'schema is invalid. error: {}'.format(e)) \
                if self.is_verbose_output else sys.exit(1)

        for e in v.iter_errors(self.provider_config):
            err = ('config file validation error originating at key: {0}, '
                   '{0}, {1}'.format('.'.join(e.path), e.message))
            validation_errors.setdefault('schema', []).append(err)
        errors = ';\n'.join(map(str, v.iter_errors(self.provider_config)))

        if errors:
            self.logger.error('VALIDATION ERROR: {0}'.format(errors))
        self.logger.error('schema validation failed!') if validation_errors \
            else self.logger.info('schema validated successfully')
        # print json.dumps(validation_errors, sort_keys=True,
        # indent=4, separators=(',', ': '))
        return validation_errors

    def get_names_updater(self):
        def updater(name):
            return self.provider_config.resources_prefix + name

        return updater

    def get_files_names_updater(self, updater):
        """ Returns a function that updates file path base on the given basic
        updater: files_names_updater(path/to/file.ext) ->
        path/to/{updater(file)}.ext """

        def files_names_updater(file_path):
            # Unpack
            p = list(os.path.split(file_path))
            base, ext = os.path.splitext(p[-1])
            # Modify
            base = updater(base)
            # Pack and return
            p[-1] = base + ext
            return os.path.join(*p)

        return files_names_updater

    def update_names_in_config(self):
        """ Modifies resources' names in files' paths in config """
        updater = self.get_names_updater()
        names_paths = [x + ('name',) for x in self.CONFIG_NAMES_TO_MODIFY]
        update_config_at_paths(
            self.provider_config,
            names_paths,
            updater,
        )
        update_config_at_paths(
            self.provider_config,
            self.CONFIG_FILES_PATHS_TO_MODIFY,
            self.get_files_names_updater(updater),
        )

    # Simplifed basic API for resources' and files' names mainpulation
    def get_updated_resource_name(self, resource_name):
        """ Returns possibly prefixed resource name,
        according to configuration """
        return self.get_names_updater()(resource_name)

    def get_updated_file_name(self, file_name):
        """ Returns possibly prefixed file name,
        according to configuration. Handles correctly file path
        and extension. """
        updater = self.get_names_updater()
        return self.get_files_names_updater(updater)(file_name)

    def _run_command_via_ssh(self, command, mgmt_ip, mgmt_ssh_user,
                             mgmt_ssh_key):
        ssh_config = self.provider_config['cloudify']['bootstrap']['ssh']

        api.env.user = mgmt_ssh_user
        api.env.key_filename = mgmt_ssh_key
        api.env.warn_only = True
        api.env.abort_on_prompts = True
        api.env.connection_attempts = ssh_config['connection_attempts']
        api.env.keepalive = 0
        api.env.linewise = False
        api.env.pool_size = 0
        api.env.skip_bad_hosts = False
        api.env.timeout = ssh_config['socket_timeout']
        api.env.forward_agent = True
        api.env.status = False
        api.env.disable_known_hosts = False

        with settings(host_string=mgmt_ip), hide('running',
                                                 'stderr',
                                                 'aborts',
                                                 'warnings'):
            return api.run(command)


# Init related commands


def get_provider_by_name(provider):
    try:
        # searching first for the standard name for providers
        # (i.e. cloudify_XXX)
        provider_module_name = 'cloudify_{0}'.format(provider)
        # print provider_module_name
        return (provider_module_name,
                utils.get_provider_module(provider_module_name))
    except exceptions.CloudifyCliError:
        # if provider was not found, search for the exact literal the
        # user requested instead
        provider_module_name = provider
        return (provider_module_name,
                utils.get_provider_module(provider_module_name))


def provider_init(provider, reset_config):
    logger = get_logger()

    provider_deprecation_notice()
    if os.path.exists(os.path.join(
            utils.get_cwd(),
            constants.CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
            constants.CLOUDIFY_WD_SETTINGS_FILE_NAME)):
        if not reset_config:
            msg = ('Current directory is already initialized. '
                   'Use the "-r" flag to force '
                   'reinitialization (might overwrite '
                   'provider configuration files if exist).')
            raise exceptions.CloudifyCliError(msg)
        else:
            # resetting provider configuration
            logger.debug('resetting configuration...')
            _provider_init(provider, reset_config)
            logger.info("Configuration reset complete")
            return

    logger.info("Initializing Cloudify")
    provider_module_name = _provider_init(provider, reset_config)
    settings = utils.CloudifyWorkingDirectorySettings()
    settings.set_provider(provider_module_name)
    settings.set_is_provider_config(True)

    utils.dump_cloudify_working_dir_settings(settings)
    utils.dump_configuration_file()

    logger.info("Initialization complete")


def _provider_init(provider, reset_config):
    """
    initializes a provider by copying its config files to the cwd.
    First, will look for a module named cloudify_#provider#.
    If not found, will look for #provider#.
    If install is True, will install the supplied provider and perform
    the search again.

    :param string provider: the provider's name
    :param bool reset_config: if True, overrides the current config.
    :rtype: `string` representing the provider's module name
    """

    logger = get_logger()

    provider_module_name, provider = get_provider_by_name(provider)

    target_file = os.path.join(utils.get_cwd(), constants.CONFIG_FILE_NAME)
    if not reset_config and os.path.exists(target_file):
        msg = ('Target directory {0} already contains a '
               'provider configuration file; '
               'use the "-r" flag to '
               'reset it back to its default values.'
               .format(os.path.dirname(target_file)))
        raise exceptions.CloudifyCliError(msg)
    else:
        # try to get the path if the provider is a module
        try:
            provider_dir = provider.__path__[0]
        # if not, assume it's in the package's dir
        except:
            provider_dir = os.path.dirname(provider.__file__)
        files_path = os.path.join(provider_dir, constants.CONFIG_FILE_NAME)
        logger.debug('Copying provider files from {0} to {1}'
                     .format(files_path, utils.get_cwd()))
        shutil.copy(files_path, utils.get_cwd())

    return provider_module_name


# Bootstrap related commands

def _update_provider_context(provider_config, provider_context):
    cloudify = provider_config['cloudify']
    agent = cloudify['agents']['config']
    min_workers = agent.get('min_workers', constants.AGENT_MIN_WORKERS)
    max_workers = agent.get('max_workers', constants.AGENT_MAX_WORKERS)
    user = agent.get('user')
    remote_execution_port = agent.get('remote_execution_port',
                                      constants.REMOTE_EXECUTION_PORT)
    compute = provider_config.get('compute', {})
    agent_servers = compute.get('agent_servers', {})
    agents_keypair = agent_servers.get('agents_keypair', {})
    agent_key_path = agents_keypair.get('private_key_path',
                                        constants.AGENT_KEY_PATH)

    workflows = cloudify.get('workflows', {})
    workflow_task_retries = workflows.get(
        'task_retries',
        constants.WORKFLOW_TASK_RETRIES)
    workflow_task_retry_interval = workflows.get(
        'retry_interval',
        constants.WORKFLOW_TASK_RETRY_INTERVAL)

    policy_engine = cloudify.get('policy_engine', {})
    policy_engine_start_timeout = policy_engine.get(
        'start_timeout',
        constants.POLICY_ENGINE_START_TIMEOUT)

    provider_context['cloudify'] = {
        'resources_prefix': provider_config.resources_prefix,
        'cloudify_agent': {
            'min_workers': min_workers,
            'max_workers': max_workers,
            'agent_key_path': agent_key_path,
            'remote_execution_port': remote_execution_port
        },
        'workflows': {
            'task_retries': workflow_task_retries,
            'task_retry_interval': workflow_task_retry_interval
        },
        'policy_engine': {
            'start_timeout': policy_engine_start_timeout
        }
    }

    if user:
        provider_context['cloudify']['cloudify_agent']['user'] = user


def provider_bootstrap(config_file_path,
                       keep_up,
                       validate_only, skip_validations):
    logger = get_logger()

    provider_deprecation_notice()
    provider_name = utils.get_provider()
    provider = utils.get_provider_module(provider_name)
    try:
        provider_dir = provider.__path__[0]
    except:
        provider_dir = os.path.dirname(provider.__file__)
    provider_config = utils.read_config(config_file_path,
                                        provider_dir)
    logger.info("Prefix for all resources: '{0}'"
                .format(provider_config.resources_prefix))
    pm = provider.ProviderManager(provider_config, cli.get_global_verbosity())
    pm.keep_up_on_failure = keep_up

    if skip_validations and validate_only:
        raise exceptions.CloudifyCliError(
            'Please choose one of skip-validations or '
            'validate-only flags, not both.')
    logger.info('Bootstrapping using {0}'.format(provider_name))
    if skip_validations:
        pm.update_names_in_config()  # Prefixes
    else:
        logger.info('Validating provider resources and configuration')
        pm.augment_schema_with_common()
        if pm.validate_schema():
            raise exceptions.CloudifyValidationError('Provider schema '
                                                     'validations failed!')
        pm.update_names_in_config()  # Prefixes
        if pm.validate():
            raise exceptions.CloudifyValidationError(
                'Provider validations failed!')
        logger.info('Provider validations completed successfully')

    if validate_only:
        return
    with utils.protected_provider_call():
        logger.info('Provisioning resources for management server...')
        params = pm.provision()

    installed = False
    provider_context = {}

    def keep_up_or_teardown():
        if keep_up:
            logger.info('topology will remain up')
        else:
            logger.info('tearing down topology'
                        ' due to bootstrap failure')
            pm.teardown(provider_context)

    if params:
        mgmt_ip, private_ip, ssh_key, ssh_user, provider_context = params
        logger.info('provisioning complete')
        logger.info('ensuring connectivity with the management server...')
        if pm.ensure_connectivity_with_management_server(
                mgmt_ip, ssh_key, ssh_user):
            logger.info('connected with the management server successfully')
            logger.info('bootstrapping the management server...')
            try:
                installed = pm.bootstrap(mgmt_ip, private_ip, ssh_key,
                                         ssh_user)
            except BaseException:
                logger.error('bootstrapping failed!')
                keep_up_or_teardown()
                raise
            logger.info('bootstrapping complete') if installed else \
                logger.error('bootstrapping failed!')
        else:
            logger.error('failed connecting to the management server!')
    else:
        logger.error('provisioning failed!')

    if installed:
        _update_provider_context(provider_config,
                                 provider_context)

        mgmt_ip = mgmt_ip.encode('utf-8')

        with utils.update_wd_settings() as wd_settings:
            wd_settings.set_management_server(mgmt_ip)
            wd_settings.set_management_key(ssh_key)
            wd_settings.set_management_user(ssh_user)
            wd_settings.set_provider_context(provider_context)

        # storing provider context on management server
        utils.get_rest_client(mgmt_ip).manager.create_context(provider_name,
                                                              provider_context)

        logger.info('management server is up at {0} '
                    '(is now set as the default management server)'
                    .format(mgmt_ip))
    else:
        keep_up_or_teardown()
        raise exceptions.CloudifyBootstrapError()


# Teardown related

def _get_provider_name_and_context(mgmt_ip):
    logger = get_logger()

    # trying to retrieve provider context from server
    try:
        response = utils.get_rest_client(mgmt_ip).manager.get_context()
        return response['name'], response['context']
    except rest_exception.CloudifyClientError as e:
        logger.warn('Failed to get provider context from server: {0}'.format(
            str(e)))

    # using the local provider context instead (if it's relevant for the
    # target server)
    cosmo_wd_settings = utils.load_cloudify_working_dir_settings()
    if cosmo_wd_settings.get_provider_context():
        default_mgmt_server_ip = cosmo_wd_settings.get_management_server()
        if default_mgmt_server_ip == mgmt_ip:
            provider_name = utils.get_provider()
            return provider_name, cosmo_wd_settings.get_provider_context()
        else:
            # the local provider context data is for a different server
            msg = "Failed to get provider context from target server"
    else:
        msg = "Provider context is not set in working directory settings (" \
              "The provider is used during the bootstrap and teardown " \
              "process. This probably means that the manager was started " \
              "manually, without the bootstrap command therefore calling " \
              "teardown is not supported)."
    raise RuntimeError(msg)


def provider_teardown(config_file_path,
                      ignore_validation):
    logger = get_logger()

    provider_deprecation_notice()
    management_ip = utils.get_management_server_ip()

    provider_name, provider_context = \
        _get_provider_name_and_context(management_ip)
    provider = utils.get_provider_module(provider_name)
    try:
        provider_dir = provider.__path__[0]
    except:
        provider_dir = os.path.dirname(provider.__file__)
    provider_config = utils.read_config(config_file_path,
                                        provider_dir)
    pm = provider.ProviderManager(provider_config, cli.get_global_verbosity())

    logger.info("tearing down {0}".format(management_ip))
    with utils.protected_provider_call():
        pm.teardown(provider_context, ignore_validation)


def provider_deprecation_notice():
    logger = get_logger()

    message = ('Notice! Provider API is deprecated and is due to be removed in'
               ' Cloudify 3.2. This API is replaced by blueprints based '
               'bootstrapping.')

    if os.name != 'nt':
        import colors

        message = colors.bold(colors.red(message))

    logger.warn(message)
