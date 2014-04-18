########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import messages

__author__ = 'ran'

# Standard
import argparse
import argcomplete
import imp
import sys
import os
import traceback
import yaml
import json
import urlparse
import urllib
import time
import shutil
import socket
import paramiko
import tempfile
from copy import deepcopy
from scp import SCPClient
from contextlib import contextmanager
import logging
import logging.config
import config
from jsonschema import ValidationError, Draft4Validator
from fabric.api import run, env, local
from fabric.context_managers import settings, hide
from os.path import expanduser

# Project
from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import CosmoManagerRestClient
from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import (CosmoManagerRestCallError,
            CosmoManagerRestCallTimeoutError,
            CosmoManagerRestCallHTTPError)
from dsl_parser.parser import parse_from_path, DSLParsingException


output_level = logging.INFO
CLOUDIFY_WD_SETTINGS_FILE_NAME = '.cloudify'

SSH_CONNECT_RETRIES = 12
SSH_CONNECT_SLEEP = 5
SSH_CONNECT_PORT = 22

CONFIG_FILE_NAME = 'cloudify-config.yaml'
DEFAULTS_CONFIG_FILE_NAME = 'cloudify-config.defaults.yaml'

CLOUDIFY_PACKAGES_PATH = '/cloudify'
CLOUDIFY_COMPONENTS_PACKAGE_PATH = '/cloudify-components'
CLOUDIFY_CORE_PACKAGE_PATH = '/cloudify-core'
CLOUDIFY_UI_PACKAGE_PATH = '/cloudify-ui'
CLOUDIFY_AGENT_PACKAGE_PATH = '/cloudify-agents'

SHELL_PIPE_TO_LOGGER = ' |& logger -i -t cosmo-bootstrap -p local0.info'
FABRIC_RETRIES = 3
FABRIC_SLEEPTIME = 3


# http://stackoverflow.com/questions/8144545/turning-off-logging-in-paramiko
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(
    logging.ERROR)


def init_logger():
    if os.path.isfile(config.LOG_DIR):
        sys.exit('file {0} exists - cloudify log directory cannot be created '
                 'there. please remove the file and try again.'
                 .format(config.LOG_DIR))
    try:
        logfile = config.LOGGER['handlers']['file']['filename']
        d = os.path.dirname(logfile)
        if not os.path.exists(d):
            os.makedirs(d)
        logging.config.dictConfig(config.LOGGER)
        lgr = logging.getLogger('main')
        lgr.setLevel(logging.INFO)
        flgr = logging.getLogger('file')
        flgr.setLevel(logging.DEBUG)
        return (lgr, flgr)
    except ValueError:
        sys.exit('could not initialize logger.'
                 ' verify your logger config'
                 ' and permissions to write to {0}'
                 .format(logfile))

# initialize logger
lgr, flgr = init_logger()


def main():
    args = _parse_args(sys.argv[1:])
    args.handler(args)


def _parse_args(args):
    # Parses the arguments using the Python argparse library

    # main parser
    parser = argparse.ArgumentParser(
        description='Installs Cosmo in an OpenStack environment')

    subparsers = parser.add_subparsers()
    parser_status = subparsers.add_parser(
        'status',
        help='Command for showing general status')
    parser_use = subparsers.add_parser(
        'use',
        help='Command for using a given management server')
    parser_init = subparsers.add_parser(
        'init',
        help='Command for initializing configuration files for installation')
    parser_bootstrap = subparsers.add_parser(
        'bootstrap',
        help='Command for bootstrapping cloudify')
    parser_teardown = subparsers.add_parser(
        'teardown',
        help='Command for tearing down cloudify')
    parser_blueprints = subparsers.add_parser(
        'blueprints',
        help='Commands for blueprints')
    parser_deployments = subparsers.add_parser(
        'deployments',
        help='Commands for deployments')
    parser_executions = subparsers.add_parser(
        'executions',
        help='Commands for executions')
    parser_workflows = subparsers.add_parser(
        'workflows',
        help='Commands for workflows')
    parser_events = subparsers.add_parser(
        'events',
        help='Commands for events'
    )

    # status subparser
    _add_management_ip_optional_argument_to_parser(parser_status)
    _set_handler_for_command(parser_status, _status)

    # use subparser
    parser_use.add_argument(
        'management_ip',
        metavar='MANAGEMENT_IP',
        type=str,
        help='The cloudify management server ip address'
    )
    parser_use.add_argument(
        '-a', '--alias',
        dest='alias',
        metavar='ALIAS',
        type=str,
        help='An alias for the management server'
    )
    _add_force_optional_argument_to_parser(
        parser_use,
        'A flag indicating authorization to overwrite the alias if it '
        'already exists')
    _set_handler_for_command(parser_use, _use_management_server)

    # init subparser
    parser_init.add_argument(
        'provider',
        metavar='PROVIDER',
        type=str,
        help='Command for initializing configuration files for a'
             ' specific provider'
    )
    parser_init.add_argument(
        '-t', '--target-dir',
        dest='target_dir',
        metavar='TARGET_DIRECTORY',
        type=str,
        default=os.getcwd(),
        help='The target directory to be initialized for the given provider'
    )
    parser_init.add_argument(
        '-r', '--reset-config',
        dest='reset_config',
        action='store_true',
        help='A flag indicating overwriting existing configuration is allowed'
    )

    parser_init.add_argument(
        '--install',
        dest='install',
        metavar='PROVIDER_MODULE_URL',
        type=str,
        help='url to provider module'
    )
    _set_handler_for_command(parser_init, _init_cosmo)

    # bootstrap subparser
    parser_bootstrap.add_argument(
        '-c', '--config-file',
        dest='config_file_path',
        metavar='CONFIG_FILE',
        default=None,
        type=str,
        help='Path to a provider configuration file'
    )

    parser_bootstrap.add_argument(
        '--keep-up-on-failure',
        dest='keep_up',
        action='store_true',
        help='A flag indicating that even if bootstrap fails,'
        ' the instance will remain running')

    parser_bootstrap.add_argument(
        '--dev-mode',
        dest='dev_mode',
        action='store_true',
        help='A flag indicating that bootstrap will be run in dev-mode,'
        ' allowing to choose specific branches to run with')

    parser_bootstrap.add_argument(
        '--skip-validations',
        dest='skip_validations',
        action='store_true',
        help='A flag indicating that bootstrap will be run without,'
        ' validating resources prior to bootstrapping the manager')

    parser_bootstrap.add_argument(
        '--validate-only',
        dest='validate_only',
        action='store_true',
        help='A flag indicating that validations will run without,'
        ' actually performing the bootstrap process.')

    _set_handler_for_command(parser_bootstrap, _bootstrap_cosmo)

    # teardown subparser
    parser_teardown.add_argument(
        '-c', '--config-file',
        dest='config_file_path',
        metavar='CONFIG_FILE',
        default=None,
        type=str,
        help='Path to a provider configuration file'
    )
    parser_teardown.add_argument(
        '--ignore-deployments',
        dest='ignore_deployments',
        action='store_true',
        help='A flag indicating confirmation for teardown even if there '
             'exist active deployments'
    )
    parser_teardown.add_argument(
        '--ignore-validation',
        dest='ignore_validation',
        action='store_true',
        help='A flag indicating confirmation for teardown even if there '
             'are validation conflicts'
    )
    _add_force_optional_argument_to_parser(
        parser_teardown,
        'A flag indicating confirmation for the teardown request')
    _add_management_ip_optional_argument_to_parser(parser_teardown)
    _set_handler_for_command(parser_teardown, _teardown_cosmo)

    # blueprints subparser
    blueprints_subparsers = parser_blueprints.add_subparsers()

    parser_blueprints_upload = blueprints_subparsers.add_parser(
        'upload',
        help='command for uploading a blueprint to the management server')
    parser_blueprints_list = blueprints_subparsers.add_parser(
        'list',
        help='command for listing all uploaded blueprints')
    parser_blueprints_delete = blueprints_subparsers.add_parser(
        'delete',
        help='command for deleting an uploaded blueprint')
    parser_blueprints_validate = blueprints_subparsers.add_parser(
        'validate',
        help='command for validating a blueprint')

    parser_blueprints_validate.add_argument(
        'blueprint_file',
        metavar='BLUEPRINT_FILE',
        type=argparse.FileType(),
        help='Path to blueprint file to be validated'
    )
    _set_handler_for_command(parser_blueprints_validate, _validate_blueprint)

    parser_blueprints_upload.add_argument(
        'blueprint_path',
        metavar='BLUEPRINT_FILE',
        type=str,
        help="Path to the application's blueprint file"
    )
    parser_blueprints_upload.add_argument(
        '-b', '--blueprint-id',
        dest='blueprint_id',
        metavar='BLUEPRINT_ID',
        type=str,
        default=None,
        required=False,
        help="Set the id of the uploaded blueprint"
    )
    _add_management_ip_optional_argument_to_parser(parser_blueprints_upload)
    _set_handler_for_command(parser_blueprints_upload, _upload_blueprint)

    _add_management_ip_optional_argument_to_parser(parser_blueprints_list)
    _set_handler_for_command(parser_blueprints_list, _list_blueprints)

    parser_blueprints_delete.add_argument(
        '-b', '--blueprint-id',
        dest='blueprint_id',
        metavar='BLUEPRINT_ID',
        type=str,
        required=True,
        help="The id of the blueprint meant for deletion"
    )
    _add_management_ip_optional_argument_to_parser(parser_blueprints_delete)
    _set_handler_for_command(parser_blueprints_delete, _delete_blueprint)

    # deployments subparser
    deployments_subparsers = parser_deployments.add_subparsers()
    parser_deployments_create = deployments_subparsers.add_parser(
        'create',
        help='command for creating a deployment of a blueprint')
    parser_deployments_execute = deployments_subparsers.add_parser(
        'execute',
        help='command for executing a deployment of a blueprint')
    parser_deployments_list = deployments_subparsers.add_parser(
        'list',
        help='command for listing all deployments or all deployments'
             'of a blueprint'
    )

    parser_deployments_create.add_argument(
        '-b', '--blueprint-id',
        dest='blueprint_id',
        metavar='BLUEPRINT_ID',
        type=str,
        required=True,
        help="The id of the blueprint meant for deployment"
    )
    parser_deployments_create.add_argument(
        '-d', '--deployment-id',
        dest='deployment_id',
        metavar='DEPLOYMENT_ID',
        type=str,
        required=True,
        help="A unique id that will be assigned to the created deployment"
    )
    _add_management_ip_optional_argument_to_parser(parser_deployments_create)
    _set_handler_for_command(parser_deployments_create, _create_deployment)

    parser_deployments_execute.add_argument(
        'operation',
        metavar='OPERATION',
        type=str,
        help='The operation to execute'
    )
    parser_deployments_execute.add_argument(
        '-d', '--deployment-id',
        dest='deployment_id',
        metavar='DEPLOYMENT_ID',
        type=str,
        required=True,
        help='The id of the deployment to execute the operation on'
    )
    parser_deployments_execute.add_argument(
        '--timeout',
        dest='timeout',
        metavar='TIMEOUT',
        type=int,
        required=False,
        default=900,
        help='Operation timeout in seconds (The execution itself will keep '
             'going, it is the CLI that will stop waiting for it to terminate)'
    )
    parser_deployments_execute.add_argument(
        '--force',
        dest='force',
        action='store_true',
        default=False,
        help='Whether the workflow should execute even if there is an ongoing'
             ' execution for the provided deployment'
    )

    _add_management_ip_optional_argument_to_parser(parser_deployments_execute)
    _set_handler_for_command(parser_deployments_execute,
                             _execute_deployment_operation)

    parser_deployments_list.add_argument(
        '-b', '--blueprint-id',
        dest='blueprint_id',
        metavar='BLUEPRINT_ID',
        type=str,
        required=False,
        help='The id of a blueprint to list deployments for'
    )
    _add_management_ip_optional_argument_to_parser(parser_deployments_list)
    _set_handler_for_command(parser_deployments_list,
                             _list_blueprint_deployments)

    # workflows subparser
    workflows_subparsers = parser_workflows.add_subparsers()
    parser_workflows_list = workflows_subparsers.add_parser(
        'list',
        help='command for listing workflows for a deployment')
    parser_workflows_list.add_argument(
        '-d', '--deployment-id',
        dest='deployment_id',
        metavar='DEPLOYMENT_ID',
        type=str,
        required=True,
        help='The id of the deployment whose workflows to list'
    )
    _add_management_ip_optional_argument_to_parser(parser_workflows_list)
    _set_handler_for_command(parser_workflows_list, _list_workflows)

    # Executions list sub parser
    executions_subparsers = parser_executions.add_subparsers()
    parser_executions_list = executions_subparsers.add_parser(
        'list',
        help='command for listing all executions of a deployment'
    )
    parser_executions_list.add_argument(
        '-d', '--deployment-id',
        dest='deployment_id',
        metavar='DEPLOYMENT_ID',
        type=str,
        required=True,
        help='The id of the deployment whose executions to list'
    )
    parser_executions_list.add_argument(
        '-s', '--statuses',
        dest='with_statuses',
        action='store_true',
        help='A flag indicating whether or not to also retrieve executions '
             'statuses'
    )
    _add_management_ip_optional_argument_to_parser(parser_executions_list)
    _set_handler_for_command(parser_executions_list,
                             _list_deployment_executions)

    parser_executions_cancel = executions_subparsers.add_parser(
        'cancel',
        help='Cancel an execution by its id'
    )
    parser_executions_cancel.add_argument(
        '-e', '--execution-id',
        dest='execution_id',
        metavar='EXECUTION_ID',
        type=str,
        required=True,
        help='The id of the execution to cancel'
    )
    _add_management_ip_optional_argument_to_parser(parser_executions_cancel)
    _set_handler_for_command(parser_executions_cancel,
                             _cancel_execution)

    parser_events.add_argument(
        '-e', '--execution-id',
        dest='execution_id',
        metavar='EXECUTION_ID',
        type=str,
        required=True,
        help='The id of the execution to get events for'
    )
    parser_events.add_argument(
        '-l', '--include-logs',
        dest='include_logs',
        action='store_true',
        help='A flag whether to include logs in returned events'
    )
    _add_management_ip_optional_argument_to_parser(parser_events)
    _set_handler_for_command(parser_events, _get_events)

    argcomplete.autocomplete(parser)
    return parser.parse_args(args)


def _get_provider_module(provider_name, is_verbose_output=False):
    try:
        module_or_pkg_desc = imp.find_module(provider_name)
        if not module_or_pkg_desc[1]:
            # module_or_pkg_desc[1] is the pathname of found module/package,
            # if it's empty none were found
            msg = ('Provider {0} not found.'
                   .format(provider_name))
            flgr.error(msg)
            raise CosmoCliError(msg) if is_verbose_output else sys.exit(msg)

        module = imp.load_module(provider_name, *module_or_pkg_desc)

        if not module_or_pkg_desc[0]:
            # module_or_pkg_desc[0] is None and module_or_pkg_desc[1] is not
            # empty only when we've loaded a package rather than a module.
            # Re-searching for the module inside the now-loaded package
            # with the same name.
            module = imp.load_module(
                provider_name,
                *imp.find_module(provider_name, module.__path__))
        return module
    except ImportError, ex:
        msg = ('Could not import module {0} '
               'maybe {0} provider module was not installed?'
               .format(provider_name))
        flgr.error(msg)
        raise CosmoCliError(str(ex)) if is_verbose_output else sys.exit(msg)


def _add_force_optional_argument_to_parser(parser, help_message):
    parser.add_argument(
        '-f', '--force',
        dest='force',
        action='store_true',
        help=help_message
    )


def _add_management_ip_optional_argument_to_parser(parser):
    parser.add_argument(
        '-t', '--management-ip',
        dest='management_ip',
        metavar='MANAGEMENT_IP',
        type=str,
        help='The cloudify management server ip address'
    )


def _set_handler_for_command(parser, handler):
    _add_verbosity_argument_to_parser(parser)

    def verbosity_aware_handler(args):
        global output_level
        if args.verbosity:
            lgr.setLevel(logging.DEBUG)
            output_level = logging.DEBUG
        handler(args)

    parser.set_defaults(handler=verbosity_aware_handler)


def _add_verbosity_argument_to_parser(parser):
    parser.add_argument(
        '-v', '--verbosity',
        dest='verbosity',
        action='store_true',
        help='A flag for setting verbose output'
    )


def set_global_verbosity_level(is_verbose_output=False):
    # we need both lgr.setLevel and the verbose_output parameter
    # since not all output is generated at the logger level.
    # verbose_output can help us control that.
    global verbose_output
    verbose_output = is_verbose_output
    if verbose_output:
        lgr.setLevel(logging.DEBUG)
    # print 'level is: ' + str(lgr.getEffectiveLevel())


def _read_config(config_file_path, provider_dir, is_verbose_output=False):

    def _deep_merge_dictionaries(overriding_dict, overridden_dict):
        merged_dict = deepcopy(overridden_dict)
        for k, v in overriding_dict.iteritems():
            if k in merged_dict and isinstance(v, dict):
                if isinstance(merged_dict[k], dict):
                    merged_dict[k] = \
                        _deep_merge_dictionaries(v, merged_dict[k])
                else:
                    raise RuntimeError('type conflict at key {0}'.format(k))
            else:
                merged_dict[k] = deepcopy(v)
        return merged_dict

    set_global_verbosity_level(is_verbose_output)
    if not config_file_path:
        config_file_path = CONFIG_FILE_NAME
    defaults_config_file_path = os.path.join(
        provider_dir,
        DEFAULTS_CONFIG_FILE_NAME)

    if not os.path.exists(config_file_path) or not os.path.exists(
            defaults_config_file_path):
        if not os.path.exists(defaults_config_file_path):
            raise ValueError('Missing the defaults configuration file; '
                             'expected to find it at {0}'.format(
                                 defaults_config_file_path))
        raise ValueError('Missing the configuration file; expected to find '
                         'it at {0}'.format(config_file_path))

    lgr.debug('reading provider config files')
    with open(config_file_path, 'r') as config_file, \
            open(defaults_config_file_path, 'r') as defaults_config_file:

        lgr.debug('safe loading user config')
        user_config = yaml.safe_load(config_file.read())

        lgr.debug('safe loading default config')
        defaults_config = yaml.safe_load(defaults_config_file.read())

    lgr.debug('merging configs')
    merged_config = _deep_merge_dictionaries(user_config, defaults_config) \
        if user_config else defaults_config
    return merged_config


def _init_cosmo(args):
    set_global_verbosity_level(args.verbosity)
    target_directory = os.path.expanduser(args.target_dir)
    provider = args.provider
    if not os.path.isdir(target_directory):
        msg = "Target directory doesn't exist."
        flgr.error(msg)
        raise CosmoCliError(msg) if args.verbosity else sys.exit(msg)

    base_instance = BaseProviderClass()
    if os.path.exists(os.path.join(target_directory,
                                   CLOUDIFY_WD_SETTINGS_FILE_NAME)):
        if not args.reset_config:
            msg = ('Target directory is already initialized. '
                   'Use the "-r" flag to force '
                   'reinitialization (might overwrite '
                   'provider configuration files if exist).')
            flgr.error(msg)
            raise CosmoCliError(msg) if args.verbosity else sys.exit(msg)

        else:  # resetting provider configuration
            lgr.debug('resetting configuration...')
            base_instance.init(provider, target_directory,
                               args.reset_config,
                               is_verbose_output=args.verbosity)
            lgr.info("Configuration reset complete")
            return

    lgr.info("Initializing Cloudify")
    provider_module_name = base_instance.init(provider, target_directory,
                                              args.reset_config,
                                              args.install,
                                              args.verbosity)
    # creating .cloudify file
    _dump_cosmo_working_dir_settings(CosmoWorkingDirectorySettings(),
                                     target_directory)
    with _update_wd_settings(args.verbosity) as wd_settings:
        wd_settings.set_provider(provider_module_name)
    lgr.info("Initialization complete")


def _bootstrap_cosmo(args):
    provider_name = _get_provider(args.verbosity)
    provider = _get_provider_module(provider_name, args.verbosity)
    provider_dir = provider.__path__[0]
    provider_config = _read_config(args.config_file_path,
                                   provider_dir,
                                   args.verbosity)
    pm = provider.ProviderManager(provider_config, args.verbosity)

    if args.skip_validations and args.validate_only:
        sys.exit('please choose one of skip_validations and '
                 'validate_only flags, not both.')
    lgr.info("bootstrapping using {0}".format(provider_name))
    if not args.skip_validations:
        lgr.info('validating provider resources and configuration')
        validation_errors = {}
        try:
            # check if ProviderManager class attr schema exists
            # and if it is, validate using the schema
            pm.schema
            validation_errors = pm.validate_schema(validation_errors,
                                                   schema=pm.schema)
        except:
            lgr.debug('schema validation disabled')
        # if the validation_errors dict return empty
        if not pm.validate(validation_errors) and not validation_errors:
            lgr.info('provider validations completed successfully')
        else:
            lgr.error('provider validations failed!')
            # TODO: raise instead.
            raise CosmoValidationError() if args.verbosity else sys.exit(1)
    if args.validate_only:
        return
    with _protected_provider_call(args.verbosity):
        lgr.info('provisioning resources for management server...')
        params = pm.provision()
    if params is not None:
        mgmt_ip, private_ip, ssh_key, ssh_user, provider_context = params
        lgr.info('provisioning complete')
        lgr.info('bootstrapping the management server...')
        installed = pm.bootstrap(mgmt_ip, private_ip, ssh_key,
                                 ssh_user, args.dev_mode)
        lgr.info('bootstrapping complete') if installed else \
            lgr.error('bootstrapping failed!')
    else:
        lgr.error('provisioning failed!')

    if params is not None and installed:
        mgmt_ip = mgmt_ip.encode('utf-8')

        with _update_wd_settings(args.verbosity) as wd_settings:
            wd_settings.set_management_server(mgmt_ip)
            wd_settings.set_provider_context(provider_context)

        # storing provider context on management server
        _get_rest_client(mgmt_ip).post_provider_context(provider_name,
                                                        provider_context)

        lgr.info(
            "management server is up at {0} (is now set as the default "
            "management server)".format(mgmt_ip))
    else:
        if args.keep_up:
            lgr.info('topology will remain up')
        else:
            lgr.info('tearing down topology'
                     ' due to bootstrap failure')
            pm.teardown(provider_context)
        raise CosmoBootstrapError() if args.verbosity else sys.exit(1)


def _teardown_cosmo(args):
    is_verbose_output = args.verbosity
    if not args.force:
        msg = ("This action requires additional "
               "confirmation. Add the '-f' or '--force' "
               "flags to your command if you are certain "
               "this command should be executed.")
        flgr.error(msg)
        raise CosmoCliError(msg) if is_verbose_output else sys.exit(msg)

    mgmt_ip = _get_management_server_ip(args)
    if not args.ignore_deployments and \
            len(_get_rest_client(mgmt_ip).list_deployments()) > 0:
        msg = ("Management server {0} has active deployments. Add the "
               "'--ignore-deployments' flag to your command to ignore "
               "these deployments and execute topology teardown."
               .format(mgmt_ip))
        flgr.error(msg)
        raise CosmoCliError(msg) if is_verbose_output else sys.exit(msg)

    provider_name, provider_context = \
        _get_provider_name_and_context(mgmt_ip, args.verbosity)
    provider = _get_provider_module(provider_name, args.verbosity)
    provider_dir = provider.__path__[0]
    provider_config = _read_config(args.config_file_path,
                                   provider_dir,
                                   args.verbosity)
    pm = provider.ProviderManager(provider_config, args.verbosity)

    lgr.info("tearing down {0}".format(mgmt_ip))
    with _protected_provider_call(args.verbosity):
        pm.teardown(provider_context, args.ignore_validation)

    # cleaning relevant data from working directory settings
    with _update_wd_settings(args.verbosity) as wd_settings:
        # wd_settings.set_provider_context(provider_context)
        wd_settings.remove_management_server_context(mgmt_ip)

    lgr.info("teardown complete")


def _get_management_server_ip(args):
    is_verbose_output = args.verbosity
    cosmo_wd_settings = _load_cosmo_working_dir_settings(is_verbose_output)
    if args.management_ip:
        return cosmo_wd_settings.translate_management_alias(
            args.management_ip)
    if cosmo_wd_settings.get_management_server():
        return cosmo_wd_settings.get_management_server()

    msg = ("Must either first run 'cfy use' command for a "
           "management server or provide a management "
           "server ip explicitly")
    flgr.error(msg)
    raise CosmoCliError(msg) if is_verbose_output else sys.exit(msg)


def _get_provider(is_verbose_output=False):
    cosmo_wd_settings = _load_cosmo_working_dir_settings(is_verbose_output)
    if cosmo_wd_settings.get_provider():
        return cosmo_wd_settings.get_provider()
    msg = "Provider is not set in working directory settings"
    flgr.error(msg)
    raise RuntimeError(msg) if is_verbose_output else sys.exit(msg)


def _get_provider_name_and_context(mgmt_ip, is_verbose_output=False):
    # trying to retrieve provider context from server
    try:
        response = _get_rest_client(mgmt_ip).get_provider_context()
        return response['name'], response['context']
    except CosmoManagerRestCallError as e:
        lgr.warn('Failed to get provider context from server: {0}'.format(
            str(e)))

    # using the local provider context instead (if it's relevant for the
    # target server)
    cosmo_wd_settings = _load_cosmo_working_dir_settings(is_verbose_output)
    if cosmo_wd_settings.get_provider_context():
        default_mgmt_server_ip = cosmo_wd_settings.get_management_server()
        if default_mgmt_server_ip == mgmt_ip:
            provider_name = _get_provider(is_verbose_output)
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
    flgr.error(msg)
    raise RuntimeError(msg) if is_verbose_output else sys.exit(msg)


def _status(args):
    management_ip = _get_management_server_ip(args)
    lgr.info(
        'querying management server {0}'.format(management_ip))

    if _check_management_server_status(management_ip):
        lgr.info(
            "REST service at management server {0} is up and running"
            .format(management_ip))
        return True
    else:
        lgr.info(
            "REST service at management server {0} is not responding"
            .format(management_ip))
        return False


def _check_management_server_status(management_ip):
    client = _get_rest_client(management_ip)
    try:
        client.status()
        return True
    except CosmoManagerRestCallError:
        return False


def _use_management_server(args):
    if not os.path.exists(CLOUDIFY_WD_SETTINGS_FILE_NAME):
        # Allowing the user to work with an existing management server
        # even if "init" wasn't called prior to this.
        _dump_cosmo_working_dir_settings(CosmoWorkingDirectorySettings())

    if not _check_management_server_status(args.management_ip):
        msg = ("Can't use management server {0}: No response.".format(
            args.management_ip))
        flgr.error(msg)
        raise CosmoCliError(msg) if args.verbosity else sys.exit(msg)

    try:
        response = _get_rest_client(args.management_ip)\
            .get_provider_context()
        provider_name = response['name']
        provider_context = response['context']
    except CosmoManagerRestCallError:
        provider_name = None
        provider_context = None

    with _update_wd_settings(args.verbosity) as wd_settings:
        wd_settings.set_management_server(
            wd_settings.translate_management_alias(args.management_ip))
        wd_settings.set_provider_context(provider_context)
        wd_settings.set_provider(provider_name)
        if args.alias:
            wd_settings.save_management_alias(args.alias,
                                              args.management_ip,
                                              args.force,
                                              args.verbosity)
            lgr.info(
                'Using management server {0} (alias {1})'.format(
                    args.management_ip, args.alias))
        else:
            lgr.info('Using management server {0}'.format(
                     args.management_ip))


def _list_blueprints(args):
    management_ip = _get_management_server_ip(args)
    lgr.info('querying blueprints list from management '
             'server {0}'.format(management_ip))
    client = _get_rest_client(management_ip)
    blueprints_list = client.list_blueprints()

    if not blueprints_list:
        lgr.info('There are no blueprints available on the '
                 'management server')
    else:
        lgr.info('Blueprints:')
        for blueprint_state in blueprints_list:
            blueprint_id = blueprint_state.id
            lgr.info('\t' + blueprint_id)


def _delete_blueprint(args):
    management_ip = _get_management_server_ip(args)
    blueprint_id = args.blueprint_id

    lgr.info(
        'Deleting blueprint {0} from management server {1}'.format(
            args.blueprint_id, management_ip))
    client = _get_rest_client(management_ip)
    client.delete_blueprint(blueprint_id)
    lgr.info("Deleted blueprint successfully")


def _upload_blueprint(args):
    is_verbose_output = args.verbosity
    blueprint_id = args.blueprint_id
    blueprint_path = os.path.expanduser(args.blueprint_path)
    if not os.path.isfile(blueprint_path):
        msg = ("Path to blueprint doesn't exist: {0}."
               .format(blueprint_path))
        flgr.error(msg)
        raise CosmoCliError(msg) if is_verbose_output else sys.exit(msg)

    management_ip = _get_management_server_ip(args)

    lgr.info(
        'Uploading blueprint {0} to management server {1}'.format(
            blueprint_path, management_ip))
    client = _get_rest_client(management_ip)
    blueprint_state = client.publish_blueprint(blueprint_path, blueprint_id)

    lgr.info(
        "Uploaded blueprint, blueprint's id is: {0}".format(
            blueprint_state.id))


def _create_deployment(args):
    blueprint_id = args.blueprint_id
    deployment_id = args.deployment_id
    management_ip = _get_management_server_ip(args)

    lgr.info('Creating new deployment from blueprint {0} at '
             'management server {1}'.format(blueprint_id, management_ip))
    client = _get_rest_client(management_ip)
    deployment = client.create_deployment(blueprint_id, deployment_id)
    lgr.info(
        "Deployment created, deployment's id is: {0}".format(
            deployment.id))


def _create_event_message_prefix(event):
    context = event['context']
    deployment_id = context['deployment_id']
    node_info = ''
    operation = ''
    if 'node_id' in context and context['node_id'] is not None:
        node_id = context['node_id']
        if 'operation' in context and context['operation'] is not None:
            operation = '.{0}'.format(context['operation'].split('.')[-1])
        node_info = '[{0}{1}] '.format(node_id, operation)
    level = 'CFY'
    message = event['message']['text'].encode('utf-8')
    if 'cloudify_log' in event['type']:
        level = 'LOG'
        message = '{0}: {1}'.format(event['level'].upper(), message)
    timestamp = event['@timestamp'].split('.')[0]

    return '{0} {1} <{2}> {3}{4}'.format(timestamp,
                                         level,
                                         deployment_id,
                                         node_info,
                                         message)


def _get_events_logger(args):
    def verbose_events_logger(events):
        for event in events:
            lgr.info(json.dumps(event, indent=4))

    def default_events_logger(events):
        for event in events:
            lgr.info(_create_event_message_prefix(event))

    if args.verbosity:
        return verbose_events_logger
    return default_events_logger


def _execute_deployment_operation(args):
    management_ip = _get_management_server_ip(args)
    operation = args.operation
    deployment_id = args.deployment_id
    timeout = args.timeout
    force = args.force

    lgr.info("Executing workflow '{0}' on deployment '{1}' at"
             " management server {2} [timeout={3} seconds]"
             .format(operation, args.deployment_id, management_ip,
                     timeout))

    events_logger = _get_events_logger(args)
    client = _get_rest_client(management_ip)

    events_message = "* Run 'cfy events --include-logs "\
                     "--execution-id {0}' for retrieving the "\
                     "execution's events/logs"

    try:
        execution_id, error = client.execute_deployment(deployment_id,
                                                        operation,
                                                        events_logger,
                                                        timeout=timeout,
                                                        force=force)
        if error is None:
            lgr.info("Finished executing workflow '{0}' on deployment"
                     "'{1}'".format(operation, deployment_id))
            lgr.info(events_message.format(execution_id))
        else:
            lgr.info("Execution of workflow '{0}' for deployment "
                     "'{1}' failed. "
                     "[error={2}]".format(operation, deployment_id, error))
            lgr.info(events_message.format(execution_id))
            raise SuppressedCosmoCliError()
    except CosmoManagerRestCallTimeoutError, e:
        lgr.info("Execution of workflow '{0}' for deployment '{1}' timed out. "
                 "* Run 'cfy executions cancel --execution-id {2}' to cancel"
                 " the running workflow.".format(operation, deployment_id,
                                                 e.execution_id))
        lgr.info(events_message.format(e.execution_id))
        raise SuppressedCosmoCliError()


# TODO implement blueprint deployments on server side
# because it is currently filter by the CLI
def _list_blueprint_deployments(args):
    blueprint_id = args.blueprint_id
    management_ip = _get_management_server_ip(args)

    message = 'Querying deployments list from management server {0}'\
              .format(management_ip)
    if blueprint_id:
        message += ' for blueprint {0}'.format(blueprint_id)
    lgr.info(message)

    client = _get_rest_client(management_ip)
    deployments = client.list_deployments()
    if blueprint_id:
        deployments = filter(lambda deployment:
                             deployment.blueprintId == blueprint_id,
                             deployments)

    if len(deployments) == 0:
        if blueprint_id:
            suffix = 'for blueprint {0}'.format(blueprint_id)
        else:
            suffix = ''
        lgr.info('There are no deployments on the management server {0}'
                 .format(suffix))
    else:
        lgr.info('Deployments:')
        for deployment in deployments:
            deployment_id = deployment.id
            if blueprint_id:
                blueprint_str = ''
            else:
                blueprint_str = ' [Blueprint: {0}]' \
                    .format(deployment.blueprintId)
            lgr.info(
                '\t' + deployment_id + blueprint_str)


def _list_workflows(args):
    management_ip = _get_management_server_ip(args)
    deployment_id = args.deployment_id

    lgr.info(
        'Querying workflows list from management server {0} for '
        'deployment {1}'.format(management_ip, args.deployment_id))
    client = _get_rest_client(management_ip)
    workflow_names = [workflow.name for workflow in
                      client.list_workflows(deployment_id).workflows]
    lgr.info("deployments workflows:")
    for name in workflow_names:
        lgr.info("\t{0}".format(name))


def _cancel_execution(args):
    management_ip = _get_management_server_ip(args)
    client = _get_rest_client(management_ip)
    execution_id = args.execution_id
    lgr.info(
        'Canceling execution {0} on management server {1}'
        .format(execution_id, management_ip))
    client.cancel_execution(execution_id)
    lgr.info(
        'Cancelled execution {0} on management server {1}'
        .format(execution_id, management_ip))


def _list_deployment_executions(args):
    is_verbose_output = args.verbosity
    management_ip = _get_management_server_ip(args)
    client = _get_rest_client(management_ip)
    deployment_id = args.deployment_id
    inc_statuses = args.with_statuses
    lgr.info(
        'Querying executions list from management server {0} for '
        'deployment {1}'.format(management_ip, deployment_id))
    try:
        executions = client.list_deployment_executions(deployment_id,
                                                       inc_statuses)
    except CosmoManagerRestCallHTTPError, e:
        if not e.status_code == 404:
            raise
        msg = ('Deployment {0} does not exist on management server'
               .format(deployment_id))
        flgr.error(msg)
        raise CosmoCliError(msg) if is_verbose_output else sys.exit(msg)

    if len(executions) == 0:
        lgr.info(
            'There are no executions on the '
            'management server for '
            'deployment {0}'.format(deployment_id))
    else:
        lgr.info(
            'Executions for deployment {0}:'.format(deployment_id))
        for execution in executions:
            lgr.info(
                '\t{0}{1}\t[deployment_id={2}, blueprint_id={3}]'.format(
                    execution.id,
                    '\t{0}'.format(execution.status) if inc_statuses else '',
                    execution.deploymentId,
                    execution.blueprintId))


def _get_events(args):
    management_ip = _get_management_server_ip(args)
    lgr.info("Getting events from management server {0} for "
             "execution id '{1}' "
             "[include_logs={2}]".format(management_ip,
                                         args.execution_id,
                                         args.include_logs))
    client = _get_rest_client(management_ip)
    try:
        events = client.get_all_execution_events(
            args.execution_id,
            include_logs=args.include_logs)
        events_logger = _get_events_logger(args)
        events_logger(events)
        lgr.info('\nTotal events: {0}'.format(len(events)))
    except CosmoManagerRestCallHTTPError, e:
        if e.status_code != 404:
            raise
        msg = ("Execution '{0}' not found on management server"
               .format(args.execution_id))
        flgr.error(msg)
        raise CosmoCliError(msg) if args.verbosity else sys.exit(msg)


def _set_cli_except_hook():
    old_excepthook = sys.excepthook

    def new_excepthook(type, value, the_traceback):
        if type == CosmoCliError:
            lgr.error(str(value))
            if output_level <= logging.DEBUG:
                print("Stack trace:")
                traceback.print_tb(the_traceback)
        elif type == CosmoManagerRestCallError:
            lgr.error("Failed making a call to REST service: {0}".format(
                      str(value)))
            if output_level <= logging.DEBUG:
                print("Stack trace:")
                traceback.print_tb(the_traceback)
        elif type == SuppressedCosmoCliError:
            # output is already generated elsewhere
            # we only want and exit code that is not 0
            pass
        else:
            old_excepthook(type, value, the_traceback)

    sys.excepthook = new_excepthook


def _load_cosmo_working_dir_settings(is_verbose_output=False):
    try:
        with open('{0}'.format(CLOUDIFY_WD_SETTINGS_FILE_NAME), 'r') as f:
            return yaml.load(f.read())
    except IOError:
        msg = ('You must first initialize by running the '
               'command "cfy init", or choose to work with '
               'an existing management server by running the '
               'command "cfy use".')
        flgr.error(msg)
        raise CosmoCliError(msg) if is_verbose_output else sys.exit(msg)


def _dump_cosmo_working_dir_settings(cosmo_wd_settings, target_dir=None):
    target_file_path = '{0}'.format(CLOUDIFY_WD_SETTINGS_FILE_NAME) if \
        not target_dir else os.path.join(target_dir,
                                         CLOUDIFY_WD_SETTINGS_FILE_NAME)
    with open(target_file_path, 'w') as f:
        f.write(yaml.dump(cosmo_wd_settings))


def _validate_blueprint(args):
    is_verbose_output = args.verbosity
    target_file = args.blueprint_file

    resources = _get_resource_base()
    mapping = resources + "cloudify/alias-mappings.yaml"

    lgr.info(
        messages.VALIDATING_BLUEPRINT.format(target_file.name))
    try:
        parse_from_path(target_file.name, None, mapping, resources)
    except DSLParsingException as ex:
        msg = (messages.VALIDATING_BLUEPRINT_FAILED
               .format(target_file, str(ex)))
        flgr.error(msg)
        raise CosmoCliError(msg) if is_verbose_output else sys.exit(msg)
    lgr.info(messages.VALIDATING_BLUEPRINT_SUCCEEDED)


def _get_resource_base():
    script_directory = os.path.dirname(os.path.realpath(__file__))
    resource_directory = script_directory \
        + "/../../cloudify-manager/resources/rest-service/"
    if os.path.isdir(resource_directory):
        lgr.debug("Found resource directory")

        resource_directory_url = urlparse.urljoin('file:', urllib.pathname2url(
            resource_directory))
        return resource_directory_url
    lgr.debug("Using resources from github. Branch is develop")
    return "https://raw.githubusercontent.com/cloudify-cosmo/" \
           "cloudify-manager/develop/resources/rest-service/"


def _get_rest_client(management_ip):
    return CosmoManagerRestClient(management_ip)


@contextmanager
def _update_wd_settings(is_verbose_output=False):
    cosmo_wd_settings = _load_cosmo_working_dir_settings(is_verbose_output)
    yield cosmo_wd_settings
    _dump_cosmo_working_dir_settings(cosmo_wd_settings)


@contextmanager
def _protected_provider_call(is_verbose_output=False):
    try:
        yield
    except Exception, ex:
        trace = sys.exc_info()[2]
        msg = ('Exception occurred in provider: {0}'
               .format(str(ex)))
        flgr.error(msg)
        raise CosmoCliError(msg), None, trace if is_verbose_output \
            else sys.exit(msg)


class CosmoWorkingDirectorySettings(yaml.YAMLObject):
    yaml_tag = u'!WD_Settings'
    yaml_loader = yaml.Loader

    def __init__(self):
        self._management_ip = None
        self._provider = None
        self._provider_context = None
        self._mgmt_aliases = {}
        self._mgmt_to_contextual_aliases = {}

    def get_management_server(self):
        return self._management_ip

    def set_management_server(self, management_ip):
        self._management_ip = management_ip

    def get_provider_context(self):
        return self._provider_context

    def set_provider_context(self, provider_context):
        self._provider_context = provider_context

    def remove_management_server_context(self, management_ip):
        # Clears management server context data.
        if management_ip in self._mgmt_to_contextual_aliases:
            del(self._mgmt_to_contextual_aliases[management_ip])

    def get_provider(self):
        return self._provider

    def set_provider(self, provider):
        self._provider = provider

    def translate_management_alias(self, management_address_or_alias):
        return self._mgmt_aliases[management_address_or_alias] if \
            management_address_or_alias in self._mgmt_aliases \
            else management_address_or_alias

    def save_management_alias(self, management_alias, management_address,
                              is_allow_overwrite, is_verbose_output=False):
        if not is_allow_overwrite and management_alias in self._mgmt_aliases:
            msg = ("management-server alias {0} is already in "
                   "use; use -f flag to allow overwrite."
                   .format(management_alias))
            flgr.error(msg)
            raise CosmoCliError(msg) if is_verbose_output else sys.exit(msg)
        self._mgmt_aliases[management_alias] = management_address


class BaseProviderClass(object):

    def init(self, provider, target_directory, reset_config, install=False,
             is_verbose_output=False):

        set_global_verbosity_level(is_verbose_output)

        def _get_provider_by_name():
            try:
                # searching first for the standard name for providers
                # (i.e. cloudify_XXX)
                provider_module_name = 'cloudify_{0}'.format(provider)
                # print provider_module_name
                return (provider_module_name,
                        _get_provider_module(provider_module_name,
                                             is_verbose_output))
            except CosmoCliError:
                # if provider was not found, search for the exact literal the
                # user requested instead
                provider_module_name = provider
                return (provider_module_name,
                        _get_provider_module(provider_module_name,
                                             is_verbose_output))
        try:
            provider_module_name, provider = _get_provider_by_name()
        except:
            if install:
                local('pip install {0} --process-dependency-links'
                      .format(install))
            provider_module_name, provider = _get_provider_by_name()

        if not reset_config and os.path.exists(
                os.path.join(target_directory, CONFIG_FILE_NAME)):
            msg = ('Target directory already contains a '
                   'provider configuration file; '
                   'use the "-r" flag to '
                   'reset it back to its default values.')
            flgr.error(msg)
            raise CosmoCliError(msg) if is_verbose_output else sys.exit(msg)
        else:
            provider_dir = provider.__path__[0]
            files_path = os.path.join(provider_dir, CONFIG_FILE_NAME)

            lgr.debug('copying provider files from {0} to {1}'
                      .format(files_path, target_directory))
            shutil.copy(files_path, target_directory)
            return provider_module_name

    def bootstrap(self, mgmt_ip, private_ip, mgmt_ssh_key, mgmt_ssh_user,
                  dev_mode=False):

        def _create_ssh_channel_with_mgmt(mgmt_ip, management_key_path,
                                          user_on_management):
            ssh = paramiko.SSHClient()
            # TODO: support fingerprint in config json
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # trying to ssh connect to management server. Using retries
            # since it might take some time to find routes to host
            for retry in range(0, SSH_CONNECT_RETRIES):
                try:
                    ssh.connect(mgmt_ip, username=user_on_management,
                                key_filename=management_key_path,
                                look_for_keys=False, timeout=10)
                    lgr.debug('ssh connection successful')
                    return ssh
                except socket.error as err:
                    lgr.debug(
                        "SSH connection to {0} failed ({1}). Waiting {2} "
                        "seconds before retrying".format(mgmt_ip, err, 5))
                    time.sleep(5)
            lgr.error('Failed to ssh connect to management server ({0}'
                      .format(err))

        def _copy_files_to_manager(ssh, userhome_on_management,
                                   keystone_config, agents_key_path,
                                   networking):
            lgr.info('uploading keystone and neutron files to manager')
            scp = SCPClient(ssh.get_transport())

            tempdir = tempfile.mkdtemp()
            try:
                scp.put(agents_key_path, userhome_on_management + '/.ssh',
                        preserve_times=True)
                keystone_file_path = _make_keystone_file(tempdir,
                                                         keystone_config)
                scp.put(keystone_file_path, userhome_on_management,
                        preserve_times=True)
                if networking['neutron_supported_region']:
                    neutron_file_path = _make_neutron_file(tempdir,
                                                           networking)
                    scp.put(neutron_file_path, userhome_on_management,
                            preserve_times=True)
            finally:
                shutil.rmtree(tempdir)

        def _make_keystone_file(tempdir, keystone_config):
            # put default region in keystone_config file
            keystone_config['region'] = \
                self.provider_config['compute']['region']
            keystone_file_path = os.path.join(tempdir, 'keystone_config.json')
            with open(keystone_file_path, 'w') as f:
                json.dump(keystone_config, f)
            return keystone_file_path

        def _make_neutron_file(tempdir, networking):
            neutron_file_path = os.path.join(tempdir, 'neutron_config.json')
            with open(neutron_file_path, 'w') as f:
                json.dump({'url': networking['neutron_url']}, f)
            return neutron_file_path

        def _exec_install_command_on_manager(ssh, install_command):
            command = 'DEBIAN_FRONTEND=noninteractive sudo -E {0}'.format(
                install_command)
            return _exec_command_on_manager(ssh, command)

        def _exec_command_on_manager(ssh, command):
            lgr.info('EXEC START: {0}'.format(command))
            chan = ssh.get_transport().open_session()
            chan.exec_command(command)
            stdin = chan.makefile('wb', -1)
            stdout = chan.makefile('rb', -1)
            stderr = chan.makefile_stderr('rb', -1)

            try:
                exit_code = chan.recv_exit_status()
                if exit_code != 0:
                    errors = stderr.readlines()
                    raise RuntimeError('Error occurred when trying to run a '
                                       'command on the management machine. '
                                       'command was: {0} ; Error(s): {1}'
                                       .format(command, errors))

                response_lines = stdout.readlines()
                lgr.info('EXEC END: {0}'.format(command))
                return response_lines
            finally:
                stdin.close()
                stdout.close()
                stderr.close()
                chan.close()

        def _get_private_key_path_from_keypair_config(keypair_config):
            path = keypair_config['provided']['private_key_filepath'] if \
                'provided' in keypair_config else \
                keypair_config['auto_generated']['private_key_target_path']
            return expanduser(path)

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
        compute_config = self.provider_config['compute']
        cosmo_config = self.provider_config['cloudify']
        mgmt_server_config = compute_config['management_server']

        lgr.debug('creating ssh channel to machine...')
        try:
            ssh = _create_ssh_channel_with_mgmt(
                mgmt_ip,
                _get_private_key_path_from_keypair_config(
                    mgmt_server_config['management_keypair']),
                mgmt_server_config['user_on_management'])
        except:
            lgr.info('ssh channel creation failed. '
                     'your private and public keys might not be matching or '
                     'your security group might not be configured to allow '
                     'connections to port {0}.'.format(SSH_CONNECT_PORT))
            return False

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

        try:
            _copy_files_to_manager(
                ssh,
                mgmt_server_config['userhome_on_management'],
                self.provider_config['keystone'],
                _get_private_key_path_from_keypair_config(
                    compute_config['agent_servers']['agents_keypair']),
                self.provider_config['networking'])
        except:
            lgr.error('failed to copy keystone files')
            return False

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

            celery_user = mgmt_server_config['user_on_management']
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

                lgr.info('managenet ip is {0}'.format(mgmt_ip))
            lgr.debug('setting verbosity to previous state')
            self.is_verbose_output = v
            return True

    def validate(self, validation_errors={}):
        lgr.debug("no resource validation methods defined!")
        return validation_errors

    def validate_schema(self, validation_errors={}, schema=None):
        lgr.debug('validating config file against provided schema...')
        v = Draft4Validator(schema)
        if v.iter_errors(self.provider_config):
            for e in v.iter_errors(self.provider_config):
                err = ('config file validation error originating at key: {0}, '
                       '{0}, {1}'.format('.'.join(e.path), e.message))
                validation_errors.setdefault('schema', []).append(err)
            errors = ';\n'.join(err for e in v.iter_errors(
                self.provider_config))
        try:
            v.validate(self.provider_config)
        except ValidationError:
            lgr.error('VALIDATION ERROR:'
                      '{0}'.format(errors))
        lgr.error('schema validation failed!') if validation_errors \
            else lgr.info('schema validated successfully')
        # print json.dumps(validation_errors, sort_keys=True,
        #                  indent=4, separators=(',', ': '))
        return validation_errors


class CosmoBootstrapError(Exception):
    pass


class CosmoValidationError(Exception):
    pass


class CosmoCliError(Exception):
    pass


class SuppressedCosmoCliError(Exception):
    pass

if __name__ == '__main__':
    _set_cli_except_hook()  # only enable hook when this is called directly.
    main()
