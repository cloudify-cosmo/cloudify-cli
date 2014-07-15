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


import argparse
import imp
import sys
import os
import traceback
import json
import urlparse
import urllib
import shutil
import time
import logging
import logging.config
import formatting
import socket
from copy import deepcopy
from contextlib import contextmanager
from platform import system
from distutils.spawn import find_executable
from subprocess import call
from StringIO import StringIO

import argcomplete
import yaml
from fabric.api import local


from dsl_parser.parser import parse_from_path, DSLParsingException
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.exceptions import CreateDeploymentInProgressError

import config
import dev
from executions import wait_for_execution
from executions import get_deployment_creation_execution
from executions import get_all_execution_events
from executions import ExecutionTimeoutError
from . import get_version_data


output_level = logging.INFO
CLOUDIFY_WD_SETTINGS_FILE_NAME = '.cloudify'

CONFIG_FILE_NAME = 'cloudify-config.yaml'
DEFAULTS_CONFIG_FILE_NAME = 'cloudify-config.defaults.yaml'

AGENT_MIN_WORKERS = 2
AGENT_MAX_WORKERS = 5
AGENT_KEY_PATH = '~/.ssh/cloudify-agents-kp.pem'
REMOTE_EXECUTION_PORT = 22

WORKFLOW_TASK_RETRIES = -1
WORKFLOW_TASK_RETRY_INTERVAL = 30

REST_PORT = 80


# http://stackoverflow.com/questions/8144545/turning-off-logging-in-paramiko
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(
    logging.ERROR)


verbose_output = False


def init_logger():
    """
    initializes a logger to be used throughout the cli
    can be used by provider codes.

    :rtype: `tupel` with 2 loggers, one for users (writes to console and file),
     and the other for archiving (writes to file only).
    """
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
    _set_cli_except_hook()
    args = _parse_args(sys.argv[1:])
    args.handler(args)


class VersionAction(argparse.Action):
    def __init__(self,
                 option_strings,
                 dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS,
                 help=None):
        super(VersionAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)

    @staticmethod
    def _format_version_data(version_data, prefix=None, suffix=None,
                             infix=None):
        all_data = version_data.copy()
        all_data['prefix'] = prefix or ''
        all_data['suffix'] = suffix or ''
        all_data['infix'] = infix or ''
        output = StringIO()
        output.write('{prefix}{version}'.format(**all_data))
        if version_data['build']:
            output.write('{infix}(build: {build}, date: {date})'.format(
                **all_data))
        output.write('{suffix}'.format(**all_data))
        return output.getvalue()

    def _get_manager_version_data(self):
        dir_settings = _load_cosmo_working_dir_settings(suppress_error=True)
        if not (dir_settings and dir_settings.get_management_server()):
            return None
        management_ip = dir_settings.get_management_server()
        if not self._connected_to_manager(management_ip):
            return None
        client = _get_rest_client(management_ip)
        try:
            version_data = client.manager.get_version()
        except CloudifyClientError:
            return None
        version_data['ip'] = management_ip
        return version_data

    @staticmethod
    def _connected_to_manager(management_ip):
        try:
            sock = socket.create_connection((management_ip, REST_PORT), 5)
            sock.close()
            return True
        except socket.error:
            return False

    def __call__(self, parser, namespace, values, option_string=None):
        cli_version_data = get_version_data()
        rest_version_data = self._get_manager_version_data()
        cli_version = self._format_version_data(
            cli_version_data,
            prefix='Cloudify CLI ',
            infix=' ' * 5,
            suffix='\n')
        rest_version = ''
        if rest_version_data:
            rest_version = self._format_version_data(
                rest_version_data,
                prefix='Cloudify Manager ',
                infix=' ',
                suffix=' [ip={ip}]\n'.format(**rest_version_data))
        parser.exit(message='{}{}'.format(cli_version,
                                          rest_version))


def _parse_args(args):
    """
    Parses the arguments using the Python argparse library.
    Generates shell autocomplete using the argcomplete library.

    :param list args: arguments from cli
    :rtype: `python argument parser`
    """
    # main parser
    parser = argparse.ArgumentParser(
        description='Manages Cloudify in different Cloud Environments')

    parser.add_argument(
        '--version',
        help='show version information and exit',
        action=VersionAction
    )

    subparsers = parser.add_subparsers()
    parser_status = subparsers.add_parser(
        'status',
        help='Show a management server\'s status'
    )
    parser_use = subparsers.add_parser(
        'use',
        help='Use/switch to the specified management server'
    )
    parser_init = subparsers.add_parser(
        'init',
        help='Initialize configuration files for a specific cloud provider'

    )
    parser_bootstrap = subparsers.add_parser(
        'bootstrap',
        help='Bootstrap Cloudify on the currently active provider'
    )
    parser_teardown = subparsers.add_parser(
        'teardown',
        help='Teardown Cloudify'
    )
    parser_blueprints = subparsers.add_parser(
        'blueprints',
        help='Manages Cloudify\'s Blueprints'
    )
    parser_deployments = subparsers.add_parser(
        'deployments',
        help='Manages and Executes Cloudify\'s Deployments'
    )
    parser_executions = subparsers.add_parser(
        'executions',
        help='Manages Cloudify Executions'
    )
    parser_workflows = subparsers.add_parser(
        'workflows',
        help='Manages Deployment Workflows'
    )
    parser_events = subparsers.add_parser(
        'events',
        help='Displays Events for different executions'
    )
    parser_dev = subparsers.add_parser(
        'dev'
    )
    parser_ssh = subparsers.add_parser(
        'ssh',
        help='SSH to management server'
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
        'already exists'
    )
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
    parser_init.add_argument(
        '--creds',
        dest='creds',
        metavar='PROVIDER_CREDENTIALS',
        type=str,
        help='a comma separated list of key=value credentials'
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
        ' the instance will remain running'
    )
    parser_bootstrap.add_argument(
        '--dev-mode',
        dest='dev_mode',
        action='store_true',
        help='A flag indicating that bootstrap will be run in dev-mode,'
        ' allowing to choose specific branches to run with'
    )
    parser_bootstrap.add_argument(
        '--skip-validations',
        dest='skip_validations',
        action='store_true',
        help='A flag indicating that bootstrap will be run without,'
        ' validating resources prior to bootstrapping the manager'
    )
    parser_bootstrap.add_argument(
        '--validate-only',
        dest='validate_only',
        action='store_true',
        help='A flag indicating that validations will run without,'
        ' actually performing the bootstrap process.'
    )
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
        help='command for uploading a blueprint to the management server'
    )
    parser_blueprints_download = blueprints_subparsers.add_parser(
        'download',
        help='command for downloading a blueprint from the management server'
    )
    parser_blueprints_list = blueprints_subparsers.add_parser(
        'list',
        help='command for listing all uploaded blueprints'
    )
    parser_blueprints_delete = blueprints_subparsers.add_parser(
        'delete',
        help='command for deleting an uploaded blueprint'
    )
    parser_blueprints_validate = blueprints_subparsers.add_parser(
        'validate',
        help='command for validating a blueprint'
    )
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
    _add_blueprint_id_argument_to_parser(
        parser_blueprints_upload,
        "Set the id of the uploaded blueprint",
        False)
    _add_management_ip_optional_argument_to_parser(parser_blueprints_upload)
    _set_handler_for_command(parser_blueprints_upload, _upload_blueprint)

    _add_management_ip_optional_argument_to_parser(parser_blueprints_list)
    _set_handler_for_command(parser_blueprints_list, _list_blueprints)

    _add_management_ip_optional_argument_to_parser(parser_blueprints_download)
    _set_handler_for_command(parser_blueprints_download, _download_blueprint)

    _add_blueprint_id_argument_to_parser(
        parser_blueprints_download,
        "The id fo the blueprint to download")
    parser_blueprints_download.add_argument(
        '-o', '--output',
        dest='output',
        metavar='OUTPUT',
        type=str,
        required=False,
        help="The output file path of the blueprint to be downloaded"
    )

    _add_blueprint_id_argument_to_parser(
        parser_blueprints_delete,
        "The id of the blueprint meant for deletion")
    _add_management_ip_optional_argument_to_parser(parser_blueprints_delete)
    _set_handler_for_command(parser_blueprints_delete, _delete_blueprint)

    # deployments subparser
    deployments_subparsers = parser_deployments.add_subparsers()
    parser_deployments_create = deployments_subparsers.add_parser(
        'create',
        help='command for creating a deployment of a blueprint'
    )
    parser_deployments_delete = deployments_subparsers.add_parser(
        'delete',
        help='command for deleting a deployment'
    )
    parser_deployments_execute = deployments_subparsers.add_parser(
        'execute',
        help='command for executing a deployment of a blueprint'
    )
    parser_deployments_list = deployments_subparsers.add_parser(
        'list',
        help='command for listing all deployments or all deployments'
             'of a blueprint'
    )
    _add_blueprint_id_argument_to_parser(
        parser_deployments_create,
        "The id of the blueprint meant for deployment")
    _add_deployment_id_argument_to_parser(
        parser_deployments_create,
        "A unique id that will be assigned to the created deployment")
    _add_management_ip_optional_argument_to_parser(parser_deployments_create)
    _set_handler_for_command(parser_deployments_create, _create_deployment)

    _add_deployment_id_argument_to_parser(
        parser_deployments_delete,
        "The deployment's id")
    parser_deployments_delete.add_argument(
        '-f', '--ignore-live-nodes',
        dest='ignore_live_nodes',
        action='store_true',
        default=False,
        help='A flag indicating whether or not to delete the deployment even '
             'if there exist live nodes for it'
    )
    _add_management_ip_optional_argument_to_parser(parser_deployments_delete)
    _set_handler_for_command(parser_deployments_delete, _delete_deployment)

    parser_deployments_execute.add_argument(
        'workflow',
        metavar='WORKFLOW',
        type=str,
        help='The workflow to execute'
    )
    parser_deployments_execute.add_argument(
        '-p', '--parameters',
        metavar='PARAMETERS',
        type=str,
        required=False,
        help='Parameters for the workflow execution (in JSON format)'
    )
    parser_deployments_execute.add_argument(
        '--allow-custom-parameters',
        dest='allow_custom_parameters',
        action='store_true',
        default=False,
        help='A flag for allowing the passing of custom parameters ('
             "parameters which were not defined in the workflow's schema in "
             'the blueprint) to the execution'
    )
    _add_deployment_id_argument_to_parser(
        parser_deployments_execute,
        'The id of the deployment to execute the operation on')
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
    _add_force_optional_argument_to_parser(
        parser_deployments_execute,
        'Whether the workflow should execute even if there is an ongoing'
        ' execution for the provided deployment')
    _add_management_ip_optional_argument_to_parser(parser_deployments_execute)
    _add_include_logs_argument_to_parser(parser_deployments_execute)
    _set_handler_for_command(parser_deployments_execute,
                             _execute_deployment_workflow)

    _add_blueprint_id_argument_to_parser(
        parser_deployments_list,
        'The id of a blueprint to list deployments for',
        False)
    _add_management_ip_optional_argument_to_parser(parser_deployments_list)
    _set_handler_for_command(parser_deployments_list,
                             _list_blueprint_deployments)

    # workflows subparser
    workflows_subparsers = parser_workflows.add_subparsers()
    parser_workflows_get = workflows_subparsers.add_parser(
        'get',
        help='command for getting a workflow by its name and deployment'
    )
    _add_deployment_id_argument_to_parser(
        parser_workflows_get,
        'The id of the deployment for which the workflow belongs')
    parser_workflows_get.add_argument(
        '-w', '--workflow-id',
        dest='workflow_id',
        metavar='WORKFLOW_ID',
        type=str,
        required=True,
        help='The id of the workflow to get'
    )
    _add_management_ip_optional_argument_to_parser(parser_workflows_get)
    _set_handler_for_command(parser_workflows_get,
                             _get_workflow)

    parser_workflows_list = workflows_subparsers.add_parser(
        'list',
        help='command for listing workflows for a deployment')
    _add_deployment_id_argument_to_parser(
        parser_workflows_list,
        'The id of the deployment whose workflows to list')
    _add_management_ip_optional_argument_to_parser(parser_workflows_list)
    _set_handler_for_command(parser_workflows_list, _list_deployment_workflows)

    # Executions list sub parser
    executions_subparsers = parser_executions.add_subparsers()
    parser_executions_get = executions_subparsers.add_parser(
        'get',
        help='command for getting an execution by its id'
    )
    _add_execution_id_argument_to_parser(
        parser_executions_get,
        'The id of the execution to get')
    _add_management_ip_optional_argument_to_parser(parser_executions_get)
    _set_handler_for_command(parser_executions_get,
                             _get_execution)

    parser_executions_list = executions_subparsers.add_parser(
        'list',
        help='command for listing all executions of a deployment'
    )
    _add_deployment_id_argument_to_parser(
        parser_executions_list,
        'The id of the deployment whose executions to list')
    _add_management_ip_optional_argument_to_parser(parser_executions_list)
    _set_handler_for_command(parser_executions_list,
                             _list_deployment_executions)

    parser_executions_cancel = executions_subparsers.add_parser(
        'cancel',
        help='Cancel an execution by its id'
    )
    _add_execution_id_argument_to_parser(
        parser_executions_cancel,
        'The id of the execution to cancel')
    _add_force_optional_argument_to_parser(
        parser_executions_cancel,
        'A flag indicating authorization to terminate the execution abruptly '
        'rather than request an orderly termination')
    _add_management_ip_optional_argument_to_parser(parser_executions_cancel)
    _set_handler_for_command(parser_executions_cancel,
                             _cancel_execution)

    _add_execution_id_argument_to_parser(
        parser_events,
        'The id of the execution to get events for')
    _add_include_logs_argument_to_parser(parser_events)
    _add_management_ip_optional_argument_to_parser(parser_events)
    _set_handler_for_command(parser_events, _get_events)

    # dev subparser
    parser_dev.add_argument(
        'task',
        metavar='TASK',
        type=str,
        help='name of fabric task to run'
    )
    parser_dev.add_argument(
        'args',
        nargs=argparse.REMAINDER,
        metavar='ARGS',
        help='arguments for the fabric task'
    )
    parser_dev.add_argument(
        '--tasks-file',
        dest='tasks_file',
        metavar='TASKS_FILE',
        type=str,
        help='Path to a tasks file'
    )
    _add_management_ip_optional_argument_to_parser(parser_dev)
    _set_handler_for_command(parser_dev, _run_dev)

    # ssh subparser
    parser_ssh.add_argument(
        '-c', '--command',
        dest='ssh_command',
        metavar='COMMAND',
        default=None,
        type=str,
        help='Execute command over SSH'
    )
    parser_ssh.add_argument(
        '-p', '--plain',
        dest='ssh_plain_mode',
        action='store_true',
        help='Leave authentication to user'
    )
    _set_handler_for_command(parser_ssh, _run_ssh)

    argcomplete.autocomplete(parser)
    parsed = parser.parse_args(args)
    set_global_verbosity_level(parsed.verbosity)
    return parsed


def _get_provider_module(provider_name):
    try:
        module_or_pkg_desc = imp.find_module(provider_name)
        if not module_or_pkg_desc[1]:
            # module_or_pkg_desc[1] is the pathname of found module/package,
            # if it's empty none were found
            msg = ('Provider {0} not found.'.format(provider_name))
            flgr.error(msg)
            raise CosmoCliError(msg)

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
    except ImportError:
        msg = ('Could not import module {0} '
               'maybe {0} provider module was not installed?'
               .format(provider_name))
        flgr.warning(msg)
        raise CosmoCliError(str(msg))


def _add_include_logs_argument_to_parser(parser):
    parser.add_argument(
        '-l', '--include-logs',
        dest='include_logs',
        action='store_true',
        help='A flag whether to include logs in returned events'
    )


def _add_force_optional_argument_to_parser(parser, help_message):
    parser.add_argument(
        '-f', '--force',
        dest='force',
        action='store_true',
        default=False,
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


def _add_blueprint_id_argument_to_parser(parser, help_message, required=True):
    parser.add_argument(
        '-b', '--blueprint-id',
        dest='blueprint_id',
        metavar='BLUEPRINT_ID',
        type=str,
        default=None,
        required=required,
        help=help_message
    )


def _add_deployment_id_argument_to_parser(parser, help_message):
    parser.add_argument(
        '-d', '--deployment-id',
        dest='deployment_id',
        metavar='DEPLOYMENT_ID',
        type=str,
        required=True,
        help=help_message
    )


def _add_execution_id_argument_to_parser(parser, help_message):
    parser.add_argument(
        '-e', '--execution-id',
        dest='execution_id',
        metavar='EXECUTION_ID',
        type=str,
        required=True,
        help=help_message
    )


def _set_handler_for_command(parser, handler):
    _add_verbosity_argument_to_parser(parser)
    parser.set_defaults(handler=handler)


def _add_verbosity_argument_to_parser(parser):
    parser.add_argument(
        '-v', '--verbosity',
        dest='verbosity',
        action='store_true',
        help='A flag for setting verbose output'
    )


def set_global_verbosity_level(is_verbose_output):
    """
    sets the global verbosity level for console and the lgr logger.

    :param bool is_verbose_output: should be output be verbose
    :rtype: `None`
    """
    # we need both lgr.setLevel and the verbose_output parameter
    # since not all output is generated at the logger level.
    # verbose_output can help us control that.
    global verbose_output
    global output_level
    verbose_output = is_verbose_output
    if verbose_output:
        output_level = logging.DEBUG
        lgr.setLevel(logging.DEBUG)
    else:
        output_level = logging.INFO
        lgr.setLevel(logging.INFO)


def get_global_verbosity():
    """
    Returns the globally set verbosity
    :return:
    """
    global verbose_output
    return verbose_output


class ProviderConfig(dict):
    @property
    def resources_prefix(self):
        return self.get('cloudify', {}).get('resources_prefix', '')


def _read_config(config_file_path, provider_dir):

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

    if not config_file_path:
        config_file_path = CONFIG_FILE_NAME
    defaults_config_file_path = os.path.join(
        provider_dir,
        DEFAULTS_CONFIG_FILE_NAME)

    if not os.path.exists(config_file_path) or not os.path.exists(
            defaults_config_file_path):
        if not os.path.exists(defaults_config_file_path):
            raise ValueError('Defaults configuration file missing; '
                             'expected to find it at {0}'.format(
                                 defaults_config_file_path))
        raise ValueError('Configuration file missing; expected to find '
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
    return ProviderConfig(merged_config)


def _init_cosmo(args):
    target_directory = os.path.expanduser(args.target_dir)
    provider = args.provider
    if not os.path.isdir(target_directory):
        msg = "Target directory doesn't exist."
        flgr.error(msg)
        raise CosmoCliError(msg)

    if os.path.exists(os.path.join(target_directory,
                                   CLOUDIFY_WD_SETTINGS_FILE_NAME)):
        if not args.reset_config:
            msg = ('Target directory is already initialized. '
                   'Use the "-r" flag to force '
                   'reinitialization (might overwrite '
                   'provider configuration files if exist).')
            flgr.error(msg)
            raise CosmoCliError(msg)

        else:  # resetting provider configuration
            lgr.debug('resetting configuration...')
            init(provider, target_directory,
                 args.reset_config,
                 creds=args.creds)
            lgr.info("Configuration reset complete")
            return

    lgr.info("Initializing Cloudify")
    provider_module_name = init(provider, target_directory,
                                args.reset_config,
                                args.install,
                                args.creds)
    # creating .cloudify file
    _dump_cosmo_working_dir_settings(CosmoWorkingDirectorySettings(),
                                     target_directory)
    with _update_wd_settings() as wd_settings:
        wd_settings.set_provider(provider_module_name)
    lgr.info("Initialization complete")


def init(provider, target_directory, reset_config, install=False,
         creds=None):
        """
        iniatializes a provider by copying its config files to the cwd.
        First, will look for a module named cloudify_#provider#.
        If not found, will look for #provider#.
        If install is True, will install the supplied provider and perform
        the search again.

        :param string provider: the provider's name
        :param string target_directory: target directory for the config files
        :param bool reset_config: if True, overrides the current config.
        :param bool install: if supplied, will also install the desired
         provider according to the given url or module name (pypi).
        :param creds: a comma separated key=value list of credential info.
         this is specific to each provider.
        :rtype: `string` representing the provider's module name
        """
        def _get_provider_by_name():
            try:
                # searching first for the standard name for providers
                # (i.e. cloudify_XXX)
                provider_module_name = 'cloudify_{0}'.format(provider)
                # print provider_module_name
                return (provider_module_name,
                        _get_provider_module(provider_module_name))
            except CosmoCliError:
                # if provider was not found, search for the exact literal the
                # user requested instead
                provider_module_name = provider
                return (provider_module_name,
                        _get_provider_module(provider_module_name))

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
            raise CosmoCliError(msg)
        else:
            # try to get the path if the provider is a module
            try:
                provider_dir = provider.__path__[0]
            # if not, assume it's in the package's dir
            except:
                provider_dir = os.path.dirname(provider.__file__)
            files_path = os.path.join(provider_dir, CONFIG_FILE_NAME)
            lgr.debug('copying provider files from {0} to {1}'
                      .format(files_path, target_directory))
            shutil.copy(files_path, target_directory)

        if creds:
            src_config_file = '{}/{}'.format(provider_dir,
                                             DEFAULTS_CONFIG_FILE_NAME)
            dst_config_file = '{}/{}'.format(target_directory,
                                             CONFIG_FILE_NAME)
            with open(src_config_file, 'r') as f:
                provider_config = yaml.load(f.read())
                # print provider_config
                # TODO: handle cases in which creds might contain ',' or '='
                if 'credentials' in provider_config.keys():
                    for cred in creds.split(','):
                        key, value = cred.split('=')
                        if key in provider_config['credentials'].keys():
                            provider_config['credentials'][key] = value
                        else:
                            lgr.error('could not find key "{0}" in config file'
                                      .format(key))
                            raise CosmoCliError('key not found')
                else:
                    lgr.error('credentials section not found in config')
            # print yaml.dump(provider_config)
            with open(dst_config_file, 'w') as f:
                f.write(yaml.dump(provider_config, default_flow_style=False))

        return provider_module_name


def _fatal_error(msg):
    flgr.error(msg)
    raise CosmoValidationError(msg)


def _bootstrap_cosmo(args):
    provider_name = _get_provider()
    provider = _get_provider_module(provider_name)
    try:
        provider_dir = provider.__path__[0]
    except:
        provider_dir = os.path.dirname(provider.__file__)
    provider_config = _read_config(args.config_file_path,
                                   provider_dir)
    lgr.info("prefix for all resources: '{0}'".
             format(provider_config.resources_prefix))
    pm = provider.ProviderManager(provider_config, get_global_verbosity())
    pm.keep_up_on_failure = args.keep_up

    if args.skip_validations and args.validate_only:
        raise CosmoCliError('please choose one of skip-validations or '
                            'validate-only flags, not both.')
    lgr.info("bootstrapping using {0}".format(provider_name))
    if args.skip_validations:
        pm.update_names_in_config()  # Prefixes
    else:
        lgr.info('validating provider resources and configuration')
        pm.augment_schema_with_common()
        if pm.validate_schema():
            _fatal_error('provider schema validations failed!')
        pm.update_names_in_config()  # Prefixes
        if pm.validate():
            _fatal_error('provider validations failed!')
        lgr.info('provider validations completed successfully')

    if args.validate_only:
        return
    with _protected_provider_call():
        lgr.info('provisioning resources for management server...')
        params = pm.provision()

    installed = False
    provider_context = {}

    def keep_up_or_teardown():
        if args.keep_up:
            lgr.info('topology will remain up')
        else:
            lgr.info('tearing down topology'
                     ' due to bootstrap failure')
            pm.teardown(provider_context)

    if params:
        mgmt_ip, private_ip, ssh_key, ssh_user, provider_context = params
        lgr.info('provisioning complete')
        lgr.info('ensuring connectivity with the management server...')
        if pm.ensure_connectivity_with_management_server(
                mgmt_ip, ssh_key, ssh_user):
            lgr.info('connected with the management server successfully')
            lgr.info('bootstrapping the management server...')
            try:
                installed = pm.bootstrap(mgmt_ip, private_ip, ssh_key,
                                         ssh_user, args.dev_mode)
            except BaseException:
                lgr.error('bootstrapping failed!')
                keep_up_or_teardown()
                raise
            lgr.info('bootstrapping complete') if installed else \
                lgr.error('bootstrapping failed!')
        else:
            lgr.error('failed connecting to the management server!')
    else:
        lgr.error('provisioning failed!')

    if installed:
        _update_provider_context(provider_config, provider_context)

        mgmt_ip = mgmt_ip.encode('utf-8')

        with _update_wd_settings() as wd_settings:
            wd_settings.set_management_server(mgmt_ip)
            wd_settings.set_management_key(ssh_key)
            wd_settings.set_management_user(ssh_user)
            wd_settings.set_provider_context(provider_context)

        # storing provider context on management server
        _get_rest_client(mgmt_ip).manager.create_context(provider_name,
                                                         provider_context)

        lgr.info(
            "management server is up at {0} (is now set as the default "
            "management server)".format(mgmt_ip))
    else:
        keep_up_or_teardown()
        raise CosmoBootstrapError()


def _update_provider_context(provider_config, provider_context):
    cloudify = provider_config['cloudify']
    agent = cloudify['agents']['config']
    min_workers = agent.get('min_workers', AGENT_MIN_WORKERS)
    max_workers = agent.get('max_workers', AGENT_MAX_WORKERS)
    user = agent.get('user')
    remote_execution_port = agent.get('remote_execution_port',
                                      REMOTE_EXECUTION_PORT)
    compute = provider_config.get('compute', {})
    agent_servers = compute.get('agent_servers', {})
    agents_keypair = agent_servers.get('agents_keypair', {})
    agent_key_path = agents_keypair.get(
        'private_key_path', AGENT_KEY_PATH)

    workflows = cloudify.get('workflows', {})
    workflow_task_retries = workflows.get('task_retries',
                                          WORKFLOW_TASK_RETRIES)
    workflow_task_retry_interval = workflows.get('retry_interval',
                                                 WORKFLOW_TASK_RETRY_INTERVAL)

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
        }
    }

    if user:
        provider_context['cloudify']['cloudify_agent']['user'] = user


def _teardown_cosmo(args):
    if not args.force:
        msg = ("This action requires additional "
               "confirmation. Add the '-f' or '--force' "
               "flags to your command if you are certain "
               "this command should be executed.")
        flgr.error(msg)
        raise CosmoCliError(msg)

    mgmt_ip = _get_management_server_ip(args)
    client = _get_rest_client(mgmt_ip)
    if not args.ignore_deployments and len(client.deployments.list()) > 0:
        msg = ("Management server {0} has active deployments. Add the "
               "'--ignore-deployments' flag to your command to ignore "
               "these deployments and execute topology teardown."
               .format(mgmt_ip))
        flgr.error(msg)
        raise CosmoCliError(msg)

    provider_name, provider_context = \
        _get_provider_name_and_context(mgmt_ip)
    provider = _get_provider_module(provider_name)
    try:
        provider_dir = provider.__path__[0]
    except:
        provider_dir = os.path.dirname(provider.__file__)
    provider_config = _read_config(args.config_file_path,
                                   provider_dir)
    pm = provider.ProviderManager(provider_config, get_global_verbosity())

    lgr.info("tearing down {0}".format(mgmt_ip))
    with _protected_provider_call():
        pm.teardown(provider_context, args.ignore_validation)

    # cleaning relevant data from working directory settings
    with _update_wd_settings() as wd_settings:
        # wd_settings.set_provider_context(provider_context)
        wd_settings.remove_management_server_context(mgmt_ip)

    lgr.info("teardown complete")


def _get_management_server_ip(args):
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    if hasattr(args, 'management_ip') and args.management_ip:
        return cosmo_wd_settings.translate_management_alias(
            args.management_ip)
    if cosmo_wd_settings.get_management_server():
        return cosmo_wd_settings.get_management_server()

    msg = ("Must either first run 'cfy use' command for a "
           "management server or provide a management "
           "server ip explicitly")
    flgr.error(msg)
    raise CosmoCliError(msg)


def _get_provider():
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    if cosmo_wd_settings.get_provider():
        return cosmo_wd_settings.get_provider()
    msg = "Provider is not set in working directory settings"
    flgr.error(msg)
    raise RuntimeError(msg)


def _get_mgmt_user():
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    if cosmo_wd_settings.get_management_user():
        return cosmo_wd_settings.get_management_user()
    msg = "Management User is not set in working directory settings"
    flgr.error(msg)
    raise RuntimeError(msg)


def _get_mgmt_key():
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    if cosmo_wd_settings.get_management_key():
        return cosmo_wd_settings.get_management_key()
    msg = "Management Key is not set in working directory settings"
    flgr.error(msg)
    raise RuntimeError(msg)


def _get_provider_name_and_context(mgmt_ip):
    # trying to retrieve provider context from server
    try:
        response = _get_rest_client(mgmt_ip).manager.get_context()
        return response['name'], response['context']
    except CloudifyClientError as e:
        lgr.warn('Failed to get provider context from server: {0}'.format(
            str(e)))

    # using the local provider context instead (if it's relevant for the
    # target server)
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    if cosmo_wd_settings.get_provider_context():
        default_mgmt_server_ip = cosmo_wd_settings.get_management_server()
        if default_mgmt_server_ip == mgmt_ip:
            provider_name = _get_provider()
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
    raise RuntimeError(msg)


def _status(args):
    management_ip = _get_management_server_ip(args)
    lgr.info(
        'Getting management services status... [ip={0}]'.format(management_ip))

    status_result = _get_management_server_status(management_ip)
    if status_result:
        services = []
        for service in status_result['services']:
            services.append({
                'service': service['display_name'].ljust(30),
                'status': service['instances'][0]['state']
                if 'instances' in service else 'unknown'
            })
        pt = formatting.table(['service', 'status'],
                              data=services)
        _output_table('Services:', pt)

        return True
    else:
        lgr.info(
            "REST service at management server {0} is not responding!"
            .format(management_ip))
        return False


def _get_management_server_status(management_ip):
    client = _get_rest_client(management_ip)
    try:
        return client.manager.get_status()
    except CloudifyClientError:
        return None


def _use_management_server(args):
    if not os.path.exists(CLOUDIFY_WD_SETTINGS_FILE_NAME):
        # Allowing the user to work with an existing management server
        # even if "init" wasn't called prior to this.
        _dump_cosmo_working_dir_settings(CosmoWorkingDirectorySettings())

    if not _get_management_server_status(args.management_ip):
        msg = ("Can't use management server {0}: No response.".format(
            args.management_ip))
        flgr.error(msg)
        raise CosmoCliError(msg)

    try:
        response = _get_rest_client(
            args.management_ip).manager.get_context()
        provider_name = response['name']
        provider_context = response['context']
    except CloudifyClientError:
        provider_name = None
        provider_context = None

    with _update_wd_settings() as wd_settings:
        wd_settings.set_management_server(
            wd_settings.translate_management_alias(args.management_ip))
        wd_settings.set_provider_context(provider_context)
        wd_settings.set_provider(provider_name)
        if args.alias:
            wd_settings.save_management_alias(args.alias,
                                              args.management_ip,
                                              args.force)
            lgr.info(
                'Using management server {0} (alias {1})'.format(
                    args.management_ip, args.alias))
        else:
            lgr.info('Using management server {0}'.format(
                     args.management_ip))


def _list_blueprints(args):
    management_ip = _get_management_server_ip(args)
    client = _get_rest_client(management_ip)

    lgr.info('Getting blueprints list... [manager={0}]'.format(management_ip))

    pt = formatting.table(['id', 'created_at', 'updated_at'],
                          data=client.blueprints.list())

    _output_table('Blueprints:', pt)


def _output_table(title, table):
    lgr.info('{0}{1}{0}{2}{0}'.format(os.linesep, title, table))


def _delete_blueprint(args):
    management_ip = _get_management_server_ip(args)
    blueprint_id = args.blueprint_id

    lgr.info(
        'Deleting blueprint {0} from management server {1}'.format(
            blueprint_id, management_ip))
    client = _get_rest_client(management_ip)
    client.blueprints.delete(blueprint_id)
    lgr.info("Deleted blueprint successfully")


def _delete_deployment(args):
    management_ip = _get_management_server_ip(args)
    deployment_id = args.deployment_id
    ignore_live_nodes = args.ignore_live_nodes

    lgr.info(
        'Deleting deployment {0} from management server {1}'.format(
            deployment_id, management_ip))
    client = _get_rest_client(management_ip)
    client.deployments.delete(deployment_id, ignore_live_nodes)
    lgr.info("Deleted deployment successfully")


def _upload_blueprint(args):
    blueprint_id = args.blueprint_id
    blueprint_path = os.path.expanduser(args.blueprint_path)
    if not os.path.isfile(blueprint_path):
        msg = ("Path to blueprint doesn't exist: {0}."
               .format(blueprint_path))
        flgr.error(msg)
        raise CosmoCliError(msg)

    management_ip = _get_management_server_ip(args)

    lgr.info(
        'Uploading blueprint {0} to management server {1}'.format(
            blueprint_path, management_ip))
    client = _get_rest_client(management_ip)
    blueprint = client.blueprints.upload(blueprint_path, blueprint_id)
    lgr.info(
        "Uploaded blueprint, blueprint's id is: {0}".format(blueprint.id))


def _create_deployment(args):
    blueprint_id = args.blueprint_id
    deployment_id = args.deployment_id
    management_ip = _get_management_server_ip(args)

    lgr.info('Creating new deployment from blueprint {0} at '
             'management server {1}'.format(blueprint_id, management_ip))
    client = _get_rest_client(management_ip)
    deployment = client.deployments.create(blueprint_id, deployment_id)
    lgr.info(
        "Deployment created, deployment's id is: {0}".format(deployment.id))


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


def _get_events_logger():
    def verbose_events_logger(events):
        for event in events:
            lgr.info(json.dumps(event, indent=4))

    def default_events_logger(events):
        for event in events:
            lgr.info(_create_event_message_prefix(event))

    if get_global_verbosity():
        return verbose_events_logger
    else:
        return default_events_logger


def _execute_deployment_workflow(args):
    management_ip = _get_management_server_ip(args)
    workflow = args.workflow
    deployment_id = args.deployment_id
    timeout = args.timeout
    force = args.force
    allow_custom_parameters = args.allow_custom_parameters
    include_logs = args.include_logs

    try:
        # load parameters JSON or use an empty parameters dict
        parameters = json.loads(args.parameters or '{}')
    except ValueError, e:
        msg = "'parameters' argument must be a valid JSON. {}".format(str(e))
        flgr.error(msg)
        raise CosmoCliError(msg)

    lgr.info("Executing workflow '{0}' on deployment '{1}' at"
             " management server {2} [timeout={3} seconds]"
             .format(workflow, args.deployment_id, management_ip,
                     timeout))

    events_logger = _get_events_logger()

    events_message = "* Run 'cfy events --include-logs "\
                     "--execution-id {0}' for retrieving the "\
                     "execution's events/logs"
    try:
        client = _get_rest_client(management_ip)
        try:
            execution = client.deployments.execute(
                deployment_id,
                workflow,
                parameters=parameters,
                allow_custom_parameters=allow_custom_parameters,
                force=force)
        except CreateDeploymentInProgressError:
            # wait for deployment creation workflow to end
            lgr.info('Deployment creation is in progress!')
            lgr.info('Waiting for deployment '
                     'creation workflow execution to finish...')
            now = time.time()
            wait_for_execution(client,
                               deployment_id,
                               get_deployment_creation_execution(
                                   client, deployment_id),
                               events_handler=events_logger,
                               include_logs=include_logs,
                               timeout=timeout)
            remaining_timeout = time.time() - now
            timeout -= remaining_timeout
            # try to execute user specified workflow
            execution = client.deployments.execute(
                deployment_id,
                workflow,
                parameters=parameters,
                allow_custom_parameters=allow_custom_parameters,
                force=force)

        execution = wait_for_execution(client,
                                       deployment_id,
                                       execution,
                                       events_handler=events_logger,
                                       include_logs=include_logs,
                                       timeout=timeout)
        if execution.error:
            lgr.info("Execution of workflow '{0}' for deployment "
                     "'{1}' failed. [error={2}]".format(workflow,
                                                        deployment_id,
                                                        execution.error))
            lgr.info(events_message.format(execution.id))
            raise SuppressedCosmoCliError()
        else:
            lgr.info("Finished executing workflow '{0}' on deployment"
                     "'{1}'".format(workflow, deployment_id))
            lgr.info(events_message.format(execution.id))
    except ExecutionTimeoutError, e:
        lgr.info("Execution of workflow '{0}' for deployment '{1}' timed out. "
                 "* Run 'cfy executions cancel --execution-id {2}' to cancel"
                 " the running workflow.".format(workflow,
                                                 deployment_id,
                                                 e.execution_id))
        lgr.info(events_message.format(e.execution_id))
        raise SuppressedCosmoCliError()


# TODO implement blueprint deployments on server side
# because it is currently filter by the CLI
def _list_blueprint_deployments(args):
    blueprint_id = args.blueprint_id
    management_ip = _get_management_server_ip(args)
    client = _get_rest_client(management_ip)
    if blueprint_id:
        lgr.info('Getting deployments list for blueprint: '
                 '\'{0}\'... [manager={1}]'.format(blueprint_id,
                                                   management_ip))
    else:
        lgr.info('Getting deployments list... '
                 '[manager={0}]'.format(management_ip))
    deployments = client.deployments.list()
    if blueprint_id:
        deployments = filter(lambda deployment:
                             deployment['blueprintId'] == blueprint_id,
                             deployments)

    pt = formatting.table(['id', 'blueprint_id', 'created_at', 'updated_at'],
                          deployments)
    _output_table('Deployments:', pt)


def _list_deployment_workflows(args):
    management_ip = _get_management_server_ip(args)
    deployment_id = args.deployment_id
    client = _get_rest_client(management_ip)

    lgr.info('Getting workflows list for deployment: '
             '\'{0}\'... [manager={1}]'.format(deployment_id, management_ip))

    deployment = client.deployments.get(deployment_id)
    workflows = deployment.workflows
    _print_workflows(workflows, deployment)


def _print_workflows(workflows, deployment):
    pt = formatting.table(['blueprint_id', 'deployment_id',
                           'name', 'created_at'],
                          data=workflows,
                          defaults={'blueprint_id': deployment.blueprint_id,
                                    'deployment_id': deployment.id})

    _output_table('Workflows:', pt)


def _cancel_execution(args):
    management_ip = _get_management_server_ip(args)
    client = _get_rest_client(management_ip)
    execution_id = args.execution_id
    force = args.force
    lgr.info(
        '{0}Cancelling execution {1} on management server {2}'
        .format('Force-' if force else '', execution_id, management_ip))
    client.executions.cancel(execution_id, force)
    lgr.info(
        'A cancel request for execution {0} has been sent to management '
        "server {1}. To track the execution's status, use:\n"
        "cfy executions get -e {0}"
        .format(execution_id, management_ip))


def _get_workflow(args):
    management_ip = _get_management_server_ip(args)
    client = _get_rest_client(management_ip)
    deployment_id = args.deployment_id
    workflow_id = args.workflow_id

    try:
        lgr.info('Getting workflow '
                 '\'{0}\' of deployment \'{1}\' [manager={2}]'
                 .format(workflow_id, deployment_id, management_ip))
        deployment = client.deployments.get(deployment_id)
        workflow = next((wf for wf in deployment.workflows if
                         wf.name == workflow_id), None)
        if not workflow:
            msg = ("Workflow '{0}' not found on management server for "
                   "deployment {1}".format(workflow_id, deployment_id))
            flgr.error(msg)
            raise CosmoCliError(msg)
    except CloudifyClientError, e:
        if e.status_code != 404:
            raise
        msg = ("Deployment '{0}' not found on management server"
               .format(deployment_id))
        flgr.error(msg)
        raise CosmoCliError(msg)

    _print_workflows([workflow], deployment)

    # print workflow parameters
    mandatory_params = []
    optional_params = []
    for param in workflow.parameters:
        if isinstance(param, basestring):
            mandatory_params.append(param)
        else:
            optional_params.append(param)

    lgr.info('Workflow Parameters:')
    lgr.info('\tMandatory Parameters:')
    for param_name in mandatory_params:
        lgr.info('\t\t{0}'.format(param_name))

    lgr.info('\tOptional Parameters:')
    for param in optional_params:
        lgr.info('\t\t{0}: \t{1}'.format(param.keys()[0], param.values()[0]))
    lgr.info('')


def _get_execution(args):
    management_ip = _get_management_server_ip(args)
    client = _get_rest_client(management_ip)
    execution_id = args.execution_id

    try:
        lgr.info('Getting execution: '
                 '\'{0}\' [manager={1}]'.format(execution_id, management_ip))
        execution = client.executions.get(execution_id)
    except CloudifyClientError, e:
        if e.status_code != 404:
            raise
        msg = ("Execution '{0}' not found on management server"
               .format(execution_id))
        flgr.error(msg)
        raise CosmoCliError(msg)

    _print_executions([execution])

    # print execution parameters
    lgr.info('Execution Parameters:')
    for param_name, param_value in execution.parameters.iteritems():
        lgr.info('\t{0}: \t{1}'.format(param_name, param_value))
    lgr.info('')


def _list_deployment_executions(args):
    management_ip = _get_management_server_ip(args)
    client = _get_rest_client(management_ip)
    deployment_id = args.deployment_id
    try:
        lgr.info('Getting executions list for deployment: '
                 '\'{0}\' [manager={1}]'.format(deployment_id, management_ip))
        executions = client.executions.list(deployment_id)
    except CloudifyClientError, e:
        if not e.status_code != 404:
            raise
        msg = ('Deployment {0} does not exist on management server'
               .format(deployment_id))
        flgr.error(msg)
        raise CosmoCliError(msg)

    _print_executions(executions)


def _print_executions(executions):
    pt = formatting.table(['id', 'workflow_id', 'status',
                           'created_at', 'error'],
                          executions)
    _output_table('Executions:', pt)


def _get_events(args):
    management_ip = _get_management_server_ip(args)
    lgr.info("Getting events from management server {0} for "
             "execution id '{1}' "
             "[include_logs={2}]".format(management_ip,
                                         args.execution_id,
                                         args.include_logs))
    client = _get_rest_client(management_ip)
    try:
        events = get_all_execution_events(client,
                                          args.execution_id,
                                          args.include_logs)
        events_logger = _get_events_logger()
        events_logger(events)
        lgr.info('\nTotal events: {0}'.format(len(events)))
    except CloudifyClientError, e:
        if e.status_code != 404:
            raise
        msg = ("Execution '{0}' not found on management server"
               .format(args.execution_id))
        flgr.error(msg)
        raise CosmoCliError(msg)


def _run_dev(args):
    management_ip = args.management_ip if args.management_ip \
        else _get_management_server_ip(args)
    dev.execute(username=_get_mgmt_user(),
                key=_get_mgmt_key(),
                ip=management_ip,
                task=args.task,
                tasks_file=args.tasks_file,
                args=args.args)


def _run_ssh(args):
    ssh_path = find_executable('ssh')
    lgr.debug('SSH executable path: {0}'.format(ssh_path or 'Not found'))
    if not ssh_path and system() == 'Windows':
        msg = messages.SSH_WIN_NOT_FOUND
        raise CosmoCliError(msg)
    elif not ssh_path:
        msg = messages.SSH_LINUX_NOT_FOUND
        raise CosmoCliError(msg)
    else:
        _ssh(ssh_path, args)


def _ssh(path, args):
    command = [path, '{0}@{1}'.format(_get_mgmt_user(),
                                      _get_management_server_ip(args))]
    if get_global_verbosity():
        command.append('-v')
    if not args.ssh_plain_mode:
        command.extend(['-i', os.path.expanduser(_get_mgmt_key())])
    if args.ssh_command:
        command.extend(['--', args.ssh_command])
    lgr.debug('executing command: {0}'.format(' '.join(command)))
    lgr.info('Trying to connect...')
    call(command)


def _set_cli_except_hook():

    def new_excepthook(tpe, value, tb):
        prefix = ''
        output_message = True
        output_traceback = output_level <= logging.DEBUG
        if issubclass(tpe, CloudifyClientError):
            prefix = 'Failed making a call to REST service: '
        elif tpe in [CosmoCliError, CosmoValidationError]:
            pass
        elif tpe in [SuppressedCosmoCliError, CosmoBootstrapError]:
            output_message = False
        else:
            prefix = '{}: '.format(tpe.__name__)
        if output_traceback:
            print("Traceback (most recent call last):")
            traceback.print_tb(tb)
        if output_message:
            lgr.error('{}{}'.format(prefix, value))

    sys.excepthook = new_excepthook


def _load_cosmo_working_dir_settings(suppress_error=False):
    try:
        with open(CLOUDIFY_WD_SETTINGS_FILE_NAME, 'r') as f:
            return yaml.load(f.read())
    except IOError:
        if suppress_error:
            return None
        msg = ('You must first initialize by running the '
               'command "cfy init", or choose to work with '
               'an existing management server by running the '
               'command "cfy use".')
        flgr.error(msg)
        raise CosmoCliError(msg)


def _dump_cosmo_working_dir_settings(cosmo_wd_settings, target_dir=None):
    target_file_path = '{0}'.format(CLOUDIFY_WD_SETTINGS_FILE_NAME) if \
        not target_dir else os.path.join(target_dir,
                                         CLOUDIFY_WD_SETTINGS_FILE_NAME)
    with open(target_file_path, 'w') as f:
        f.write(yaml.dump(cosmo_wd_settings))


def _download_blueprint(args):
    lgr.info(messages.DOWNLOADING_BLUEPRINT.format(args.blueprint_id))
    client = _get_rest_client(_get_management_server_ip(args))
    target_file = client.blueprints.download(args.blueprint_id, args.output)
    lgr.info(messages.DOWNLOADING_BLUEPRINT_SUCCEEDED.format(
        args.blueprint_id,
        target_file))


def _validate_blueprint(args):
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
        raise CosmoCliError(msg)
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
    return CloudifyClient(management_ip)


@contextmanager
def _update_wd_settings():
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    yield cosmo_wd_settings
    _dump_cosmo_working_dir_settings(cosmo_wd_settings)


@contextmanager
def _protected_provider_call():
    try:
        yield
    except Exception, ex:
        trace = sys.exc_info()[2]
        msg = ('Exception occurred in provider: {0}'.format(str(ex)))
        flgr.error(msg)
        raise CosmoCliError(msg), None, trace


class CosmoWorkingDirectorySettings(yaml.YAMLObject):
    yaml_tag = u'!WD_Settings'
    yaml_loader = yaml.Loader

    def __init__(self):
        self._management_ip = None
        self._management_key = None
        self._management_user = None
        self._provider = None
        self._provider_context = None
        self._mgmt_aliases = {}
        self._mgmt_to_contextual_aliases = {}

    def get_management_server(self):
        return self._management_ip

    def set_management_server(self, management_ip):
        self._management_ip = management_ip

    def get_management_key(self):
        return self._management_key

    def set_management_key(self, management_key):
        self._management_key = management_key

    def get_management_user(self):
        return self._management_user

    def set_management_user(self, _management_user):
        self._management_user = _management_user

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
                              is_allow_overwrite):
        if not is_allow_overwrite and management_alias in self._mgmt_aliases:
            msg = ("management-server alias {0} is already in "
                   "use; use -f flag to allow overwrite."
                   .format(management_alias))
            flgr.error(msg)
            raise CosmoCliError(msg)
        self._mgmt_aliases[management_alias] = management_address


class CosmoBootstrapError(Exception):
    pass


class CosmoValidationError(Exception):
    pass


class CosmoCliError(Exception):
    pass


class SuppressedCosmoCliError(Exception):
    pass

if __name__ == '__main__':
    main()
