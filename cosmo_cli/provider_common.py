from abc import abstractmethod, ABCMeta
import os
import random
import string
import sys
import time

from jsonschema import ValidationError, Draft4Validator
from fabric.api import run, env
from fabric.context_managers import settings, hide

from cosmo_cli import set_global_verbosity_level, init_logger

lgr, flgr = init_logger()

CLOUDIFY_PACKAGES_PATH = '/cloudify'
CLOUDIFY_COMPONENTS_PACKAGE_PATH = '/cloudify-components'
CLOUDIFY_CORE_PACKAGE_PATH = '/cloudify-core'
CLOUDIFY_UI_PACKAGE_PATH = '/cloudify-ui'
CLOUDIFY_AGENT_PACKAGE_PATH = '/cloudify-agents'

FABRIC_RETRIES = 3
FABRIC_SLEEPTIME = 3


def update_config_at_paths(struct, paths, f):

    """ Transforms "name" property at given paths using the "f" function.
    Ignores non-existing paths. """

    def kern(struct, path):
        if not path:
            return
        if path[0] not in struct:
            return
        if len(path) == 1:
            struct[path[0]] = f(struct[path[0]])
            return
        kern(struct[path[0]], path[1:])

    for path in paths:
        kern(struct, path)


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

    def __init__(self, provider_config=None, is_verbose_output=False):

        set_global_verbosity_level(is_verbose_output)
        self.provider_config = provider_config
        self.is_verbose_output = is_verbose_output

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
         provisioned resources will remain. If the flag is ommited, they will
         be torn down.
        """
        env.user = mgmt_ssh_user
        env.key_filename = mgmt_ssh_key
        env.warn_only = True
        env.abort_on_prompts = False
        env.connection_attempts = 5
        env.keepalive = 0
        env.linewise = False
        env.pool_size = 0
        env.skip_bad_hosts = False
        env.timeout = 10
        env.forward_agent = True
        env.status = False
        env.disable_known_hosts = False

        def _run_with_retries(command, retries=FABRIC_RETRIES,
                              sleeper=FABRIC_SLEEPTIME):

            for execution in range(retries):
                lgr.debug('running command: {0}'
                          .format(command))
                if not self.is_verbose_output:
                    with hide('running', 'stdout'):
                        r = run(command)
                else:
                    r = run(command)
                if r.succeeded:
                    lgr.debug('successfully ran command: {0}'
                              .format(command))
                    return True
                else:
                    lgr.warning('retrying command: {0}'
                                .format(command))
                    time.sleep(sleeper)
            lgr.error('failed to run: {0}, {1}'
                      .format(command, r.stderr))
            return False

        def _download_package(url, path):
            return _run_with_retries('sudo wget {0} -P {1}'
                                     .format(path, url))

        def _unpack(path):
            return _run_with_retries('sudo dpkg -i {0}/*.deb'
                                     .format(path))

        def _run(command):
            return _run_with_retries(command)

        lgr.info('initializing manager on the machine at {0}'
                 .format(mgmt_ip))
        cosmo_config = self.provider_config['cloudify']
        print cosmo_config

        with settings(host_string=mgmt_ip), hide('running',
                                                 'stderr',
                                                 'aborts',
                                                 'warnings'):

            lgr.info('downloading cloudify-components package...')
            r = _download_package(
                CLOUDIFY_PACKAGES_PATH,
                cosmo_config['cloudify_components_package_url'])
            if not r:
                lgr.error('failed to download components package. '
                          'please ensure package exists in its '
                          'configured location in the config file')
                return False

            lgr.info('downloading cloudify-core package...')
            r = _download_package(
                CLOUDIFY_PACKAGES_PATH,
                cosmo_config['cloudify_core_package_url'])
            if not r:
                lgr.error('failed to download core package. '
                          'please ensure package exists in its '
                          'configured location in the config file')
                return False

            lgr.info('downloading cloudify-ui...')
            r = _download_package(
                CLOUDIFY_UI_PACKAGE_PATH,
                cosmo_config['cloudify_ui_package_url'])
            if not r:
                lgr.error('failed to download ui package. '
                          'please ensure package exists in its '
                          'configured location in the config file')
                return False

            lgr.info('downloading cloudify-ubuntu-agent...')
            r = _download_package(
                CLOUDIFY_AGENT_PACKAGE_PATH,
                cosmo_config['cloudify_ubuntu_agent_url'])
            if not r:
                lgr.error('failed to download ubuntu agent. '
                          'please ensure package exists in its '
                          'configured location in the config file')
                return False

            lgr.info('unpacking cloudify-core packages...')
            r = _unpack(
                CLOUDIFY_PACKAGES_PATH)
            if not r:
                lgr.error('failed to unpack cloudify-core package')
                return False

            lgr.debug('verifying verbosity for installation process')
            v = self.is_verbose_output
            self.is_verbose_output = True

            lgr.info('installing cloudify on {0}...'.format(mgmt_ip))
            r = _run('sudo {0}/cloudify-components-bootstrap.sh'
                     .format(CLOUDIFY_COMPONENTS_PACKAGE_PATH))
            if not r:
                lgr.error('failed to install cloudify-components')
                return False

            celery_user = mgmt_ssh_user
            r = _run('sudo {0}/cloudify-core-bootstrap.sh {1} {2}'
                     .format(CLOUDIFY_CORE_PACKAGE_PATH,
                             celery_user, private_ip))
            if not r:
                lgr.error('failed to install cloudify-core')
                return False

            lgr.info('deploying cloudify-ui')
            self.is_verbose_output = False
            r = _unpack(
                CLOUDIFY_UI_PACKAGE_PATH)
            if not r:
                lgr.error('failed to install cloudify-ui')
                return False
            lgr.info('done')

            lgr.info('deploying cloudify agent')
            self.is_verbose_output = False
            r = _unpack(
                CLOUDIFY_AGENT_PACKAGE_PATH)
            if not r:
                lgr.error('failed to install cloudify-agent')
                return False
            lgr.info('done')

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

    def augment_schema_with_common(self):
        self.schema.setdefault('type', 'object')
        self.schema.setdefault('properties', {}).update({
            "prefix_for_all_resources": {
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
        :rtype: `dict` of validaiton_errors.
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

        config = self.provider_config
        pfx = config.get('prefix_for_all_resources', '')

        def updater(name):
            return pfx + name

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
