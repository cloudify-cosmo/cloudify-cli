from abc import abstractmethod, ABCMeta
import socket
import os
import sys
import time

from jsonschema import ValidationError, Draft4Validator
from fabric.api import run, env
from fabric.context_managers import settings, hide, cd
from cosmo_cli import set_global_verbosity_level, init_logger
from os import path
import urllib2


lgr, flgr = init_logger()

CLOUDIFY_PACKAGES_PATH = '/cloudify'
CLOUDIFY_COMPONENTS_PACKAGE_PATH = '/cloudify-components'
CLOUDIFY_CORE_PACKAGE_PATH = '/cloudify-core'
CLOUDIFY_UI_PACKAGE_PATH = '/cloudify-ui'
CLOUDIFY_AGENT_PACKAGE_PATH = '/cloudify-agents'


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
    this is the basic provider class supplied with the CLI. it can be imported
     by the provider's code by inheritence into the ProviderManager class.
     each of the below methods can be overriden in favor of a different impl.
    """
    __metaclass__ = ABCMeta

    schema = {}
    CONFIG_NAMES_TO_MODIFY = ()  # No default (empty tuple)
    CONFIG_FILES_PATHS_TO_MODIFY = ()  # No default (empty tuple)

    def __init__(self, provider_config, is_verbose_output):

        set_global_verbosity_level(is_verbose_output)
        self.provider_config = provider_config
        self.is_verbose_output = is_verbose_output
        self.keep_up_on_failure = False

    @abstractmethod
    def provision(self):
        """
        provisions resources for the management server
        """
        return

    @abstractmethod
    def validate(self):
        """
        validations to be performed before provisioning and bootstrapping
        the management server.

        :param dict validation_errors: dict to hold all validation errors.
        :rtype: `dict` of validaiton_errors.
        """
        lgr.debug("no resource validation methods defined!")
        return {}

    @abstractmethod
    def teardown(self, provider_context, ignore_validation=False):
        """
        tears down the management server and its accompanied provisioned
        resources
        """
        return

    def bootstrap(self, mgmt_ip, private_ip, mgmt_ssh_key, mgmt_ssh_user,
                  dev_mode=False):
        """
        bootstraps Cloudify on the management server.

        :param string mgmt_ip: public ip of the provisioned instance.
        :param string private_ip: private ip of the provisioned instance.
         (for configuration purposes).
        :param string mgmt_ssh_key: path to the ssh key to be used for
         connecting to the instance.
        :param string mgmt_ssh_user: the user to use when connecting to the
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
                lgr.debug('running command: {0}'.format(command))
                try:
                    if not self.is_verbose_output:
                        with hide('running', 'stdout'):
                            r = self._run_command_via_ssh(command, mgmt_ip,
                                                          mgmt_ssh_user,
                                                          mgmt_ssh_key)
                    else:
                        r = self._run_command_via_ssh(command, mgmt_ip,
                                                      mgmt_ssh_user,
                                                      mgmt_ssh_key)
                except BaseException as e:
                    lgr.warning('Error occurred while running command: '
                                '{}'.format(str(e)))
                    error_message = str(e)
                if r and r.succeeded:
                    lgr.debug('successfully ran command: {0}'.format(command))
                    return r.stdout if return_output_on_success else True
                elif r:
                    error_message = r.stderr
                lgr.warning('retrying command: {0}'.format(command))
                time.sleep(sleeper)
            lgr.error('failed to run: {0}, {1}'
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
            lgr.debug('checking distro-type match for url: {}'.format(url))
            ext = get_ext(url)
            if not DISTRO_EXT[distro] == ext:
                lgr.error('wrong package type: '
                          '{} required. {} supplied. in url: {}'
                          .format(DISTRO_EXT[distro], ext, url))
                return False
            return True

        def get_distro():
            lgr.debug('identifying instance distribution...')
            return _run_with_retries(
                'python -c "import platform; print platform.dist()[0]"',
                return_output_on_success=True)

        def get_ext(url):
            lgr.debug('extracting file extension from url')
            file = urllib2.unquote(url).decode('utf8').split('/')[-1]
            return path.splitext(file)[1]

        def _run(command):
            return _run_with_retries(command)

        lgr.info('initializing manager on the machine at {0}'.format(mgmt_ip))
        cloudify_config = self.provider_config['cloudify']

        server_packages = cloudify_config['server']['packages']
        agent_packages = cloudify_config['agents']['packages']
        ui_included = True if 'ui_package_url' in server_packages \
            else False
        # get linux distribution to install and download
        # packages accordingly
        dist = get_distro()  # dist is either the dist name or False
        if dist:
            lgr.debug('distribution is: {0}'.format(dist))
        else:
            lgr.error('could not identify distribution.')
            return False

        # check package compatibility with current distro
        lgr.debug('checking package-distro compatibility')
        for package, package_url in server_packages.items():
            if not check_distro_type_match(package_url, dist):
                raise RuntimeError('wrong package type')
        for package, package_url in agent_packages.items():
            if not check_distro_type_match(package_url, dist):
                raise RuntimeError('wrong agent package type')

        # TODO: consolidate server package downloading
        lgr.info('downloading cloudify-components package...')
        success = _download_package(
            CLOUDIFY_PACKAGES_PATH,
            server_packages['components_package_url'],
            dist)
        if not success:
            lgr.error('failed to download components package. '
                      'please ensure package exists in its '
                      'configured location in the config file')
            return False

        lgr.info('downloading cloudify-core package...')
        success = _download_package(
            CLOUDIFY_PACKAGES_PATH,
            server_packages['core_package_url'],
            dist)
        if not success:
            lgr.error('failed to download core package. '
                      'please ensure package exists in its '
                      'configured location in the config file')
            return False

        if ui_included:
            lgr.info('downloading cloudify-ui...')
            success = _download_package(
                CLOUDIFY_UI_PACKAGE_PATH,
                server_packages['ui_package_url'],
                dist)
            if not success:
                lgr.error('failed to download ui package. '
                          'please ensure package exists in its '
                          'configured location in the config file')
                return False
        else:
            lgr.debug('ui url not configured in provider config. '
                      'skipping ui installation.')

        for agent, agent_url in \
                agent_packages.items():
            success = _download_package(
                CLOUDIFY_AGENT_PACKAGE_PATH,
                agent_packages[agent],
                dist)
            if not success:
                lgr.error('failed to download {}. '
                          'please ensure package exists in its '
                          'configured location in the config file'.format(
                              agent_url))
                return False

        lgr.info('unpacking cloudify-core packages...')
        success = _unpack(
            CLOUDIFY_PACKAGES_PATH,
            dist)
        if not success:
            lgr.error('failed to unpack cloudify-core package.')
            return False

        lgr.debug('verifying verbosity for installation process.')
        v = self.is_verbose_output
        self.is_verbose_output = True

        lgr.info('installing cloudify on {0}...'.format(mgmt_ip))
        success = _run('sudo {0}/cloudify-components-bootstrap.sh'.format(
            CLOUDIFY_COMPONENTS_PACKAGE_PATH))
        if not success:
            lgr.error('failed to install cloudify-components package.')
            return False

        # declare user to run celery. this is passed to the core package's
        # bootstrap script for installation.
        celery_user = mgmt_ssh_user
        success = _run('sudo {0}/cloudify-core-bootstrap.sh {1} {2}'.format(
            CLOUDIFY_CORE_PACKAGE_PATH, celery_user, private_ip))
        if not success:
            lgr.error('failed to install cloudify-core package.')
            return False

        if ui_included:
            lgr.info('installing cloudify-ui...')
            self.is_verbose_output = False
            success = _unpack(
                CLOUDIFY_UI_PACKAGE_PATH,
                dist)
            if not success:
                lgr.error('failed to install cloudify-ui.')
                return False
            lgr.info('cloudify-ui installation successful.')

        lgr.info('deploying cloudify agents')
        self.is_verbose_output = False
        success = _unpack(
            CLOUDIFY_AGENT_PACKAGE_PATH,
            dist)
        if not success:
            lgr.error('failed to install cloudify agents.')
            return False
        lgr.info('cloudify agents installation successful.')

        self.is_verbose_output = True
        if dev_mode:
            lgr.info('\n\n\n\n\nentering dev-mode. '
                     'dev configuration will be applied...\n'
                     'NOTE: an internet connection might be '
                     'required...')

            dev_config = self.provider_config['dev']
            # lgr.debug(json.dumps(dev_config, sort_keys=True,
            #           indent=4, separators=(',', ': ')))

            for key, value in dev_config.iteritems():
                virtualenv = value['virtualenv']
                lgr.debug('virtualenv is: ' + str(virtualenv))

                if 'preruns' in value:
                    for command in value['preruns']:
                        _run(command)

                if 'downloads' in value:
                    _run('mkdir -p /tmp/{0}'.format(virtualenv))
                    for download in value['downloads']:
                        lgr.debug('downloading: ' + download)
                        _run('sudo wget {0} -O '
                             '/tmp/module.tar.gz'
                             .format(download))
                        _run('sudo tar -C /tmp/{0} -xvf {1}'
                             .format(virtualenv,
                                     '/tmp/module.tar.gz'))

                if 'installs' in value:
                    for module in value['installs']:
                        lgr.debug('installing: ' + module)
                        if module.startswith('/'):
                            module = '/tmp' + virtualenv + module
                        _run('sudo {0}/bin/pip '
                             '--default-timeout'
                             '=45 install {1} --upgrade'
                             ' --process-dependency-links'
                             .format(virtualenv, module))
                if 'runs' in value:
                    for command in value['runs']:
                        _run(command)

            lgr.info('management ip is {0}'.format(mgmt_ip))
        lgr.debug('setting verbosity to previous state')
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
                log_func = lgr.info if \
                    retry >= num_of_retries_without_log_message else lgr.debug
                log_func('Trying to open an SSH socket to management machine '
                         '(attempt {0} of {1})'.format(retry + 1, retries))

                sock = socket.create_connection((mgmt_ip, 22), socket_timeout)
                sock.close()
                break
            except (socket.timeout, socket.error) as e:
                # note: This could possibly be a '[Errno 110] Connection timed
                # out' error caused by the network stack, which has a different
                # timeout setting than the one used for the python socket.
                lgr.debug('Error occurred in initial connectivity check with '
                          'management server: {}'.format(str(e)))
            time.sleep(retries_interval)
        else:
            lgr.error('Failed to open an SSH socket to management machine '
                      '(tried {0} times)'.format(retries))
            return False

        test_ssh_cmd = ''
        try:
            self._run_command_via_ssh(test_ssh_cmd, mgmt_ip,
                                      mgmt_ssh_user, mgmt_ssh_key)
            return True
        except BaseException as e:
            lgr.error('Error occurred while trying to SSH connect to '
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
            lgr.warn('schema is not provided in class "{0}", skipping schema '
                     'validation'.format(self.__class__))
            return {}

        validation_errors = {}
        lgr.debug('validating config file against provided schema...')
        try:
            v = Draft4Validator(self.schema)
        except AttributeError as e:
            flgr.error('schema is invalid. error: {}'.format(e))
            raise ValidationError('schema is invalid. error: {}'.format(e)) \
                if self.is_verbose_output else sys.exit(1)

        for e in v.iter_errors(self.provider_config):
            err = ('config file validation error originating at key: {0}, '
                   '{0}, {1}'.format('.'.join(e.path), e.message))
            validation_errors.setdefault('schema', []).append(err)
        errors = ';\n'.join(map(str, v.iter_errors(self.provider_config)))

        if errors:
            lgr.error('VALIDATION ERROR: {0}'.format(errors))
        lgr.error('schema validation failed!') if validation_errors \
            else lgr.info('schema validated successfully')
        # print json.dumps(validation_errors, sort_keys=True,
        #                  indent=4, separators=(',', ': '))
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

        env.user = mgmt_ssh_user
        env.key_filename = mgmt_ssh_key
        env.warn_only = True
        env.abort_on_prompts = True
        env.connection_attempts = ssh_config['connection_attempts']
        env.keepalive = 0
        env.linewise = False
        env.pool_size = 0
        env.skip_bad_hosts = False
        env.timeout = ssh_config['socket_timeout']
        env.forward_agent = True
        env.status = False
        env.disable_known_hosts = False

        with settings(host_string=mgmt_ip), hide('running',
                                                 'stderr',
                                                 'aborts',
                                                 'warnings'):
            return run(command)
