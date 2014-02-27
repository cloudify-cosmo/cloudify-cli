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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
import messages

__author__ = 'ran'

# Standard
import argparse
import imp
import sys
import os
import traceback
import yaml
import json
import urlparse
import urllib
from contextlib import contextmanager
import logging
import logging.config
import config

# Project
from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import CosmoManagerRestClient
from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import CosmoManagerRestCallError
from dsl_parser.parser import parse_from_path, DSLParsingException


output_level = logging.INFO
CLOUDIFY_WD_SETTINGS_FILE_NAME = '.cloudify'


#initialize logger
try:
    d = os.path.dirname(config.LOGGER['handlers']['file']['filename'])
    if not os.path.exists(d):
        os.makedirs(d)
    logging.config.dictConfig(config.LOGGER)
    lgr = logging.getLogger('main')
    lgr.setLevel(logging.INFO)
except ValueError:
    sys.exit('could not initialize logger.'
             ' verify your logger config'
             ' and permissions to write to {0}'
             .format(config.LOGGER['handlers']['file']['filename']))


def main():
    args = _parse_args(sys.argv[1:])
    args.handler(args)


def _parse_args(args):
    #Parses the arguments using the Python argparse library

    #main parser
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

    #status subparser
    _add_management_ip_optional_argument_to_parser(parser_status)
    _set_handler_for_command(parser_status, _status)

    #use subparser
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

    #init subparser
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
    _set_handler_for_command(parser_init, _init_cosmo)

    #bootstrap subparser
    parser_bootstrap.add_argument(
        '-c', '--config-file',
        dest='config_file_path',
        metavar='CONFIG_FILE',
        default=None,
        type=str,
        help='Path to a provider configuration file'
    )

    parser_bootstrap.add_argument(
        '-a', '--alternate-bootstrap-method',
        dest='bootstrap_using_script',
        action='store_true',
        help='A flag indicating bootstrap will be performed via a script')
    _set_handler_for_command(parser_bootstrap, _bootstrap_cosmo)

    #teardown subparser
    _add_force_optional_argument_to_parser(
        parser_teardown,
        'A flag indicating confirmation for the teardown request')
    _add_management_ip_optional_argument_to_parser(parser_teardown)
    _set_handler_for_command(parser_teardown, _teardown_cosmo)

    #blueprints subparser
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

    #deployments subparser
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

    #workflows subparser
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

    _add_management_ip_optional_argument_to_parser(parser_executions_list)
    _set_handler_for_command(parser_executions_list,
                             _list_deployment_executions)

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

    return parser.parse_args(args)


def _get_provider_module(provider_name, is_verbose_output=False):
    try:
        module_or_pkg_desc = imp.find_module(provider_name)
        if not module_or_pkg_desc[1]:
            #module_or_pkg_desc[1] is the pathname of found module/package,
            #if it's empty none were found
            msg = ('Provider {0} not found.'
                   .format(provider_name))
            if is_verbose_output:
                raise CosmoCliError(msg)
            else:
                lgr.error(msg)
                raise

        module = imp.load_module(provider_name, *module_or_pkg_desc)

        if not module_or_pkg_desc[0]:
            #module_or_pkg_desc[0] is None and module_or_pkg_desc[1] is not
            #empty only when we've loaded a package rather than a module.
            #Re-searching for the module inside the now-loaded package
            #with the same name.
            module = imp.load_module(
                provider_name,
                *imp.find_module(provider_name, module.__path__))
        return module
    except ImportError, ex:
        if is_verbose_output:
            raise CosmoCliError(str(ex))
        else:
            lgr.error('Could not import module {0} '
                      'maybe {0} provider module was not installed?'
                      .format(provider_name))
            raise


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


def _init_provider(provider, target_directory, reset_config,
                   is_verbose_output=False):
    try:
        #searching first for the standard name for providers
        #(i.e. cloudify_XXX)
        provider_module_name = 'cloudify_{0}'.format(provider)
        provider = _get_provider_module(provider_module_name,
                                        is_verbose_output)
    except CosmoCliError:
        #if provider was not found, search for the exact literal the
        #user requested instead
        provider_module_name = provider
        provider = _get_provider_module(provider_module_name,
                                        is_verbose_output)
    with _protected_provider_call(is_verbose_output):
        success = provider.init(target_directory, reset_config,
                                is_verbose_output)
        if not success:
            msg = ('Target directory already contains a '
                   'provider configuration file; '
                   'use the "-r" flag to '
                   'reset it back to its default values.')
            if is_verbose_output:
                raise CosmoCliError(msg)
            else:
                lgr.error(msg)
                raise

    return provider_module_name


def _init_cosmo(args):

    is_verbose_output = args.verbosity
    target_directory = os.path.expanduser(args.target_dir)
    provider = args.provider
    if not os.path.isdir(target_directory):
        msg = "Target directory doesn't exist."
        if is_verbose_output:
            raise CosmoCliError(msg)
        else:
            lgr.error(msg)
            raise

    is_verbose_output = args.verbosity
    if os.path.exists(os.path.join(target_directory,
                                   CLOUDIFY_WD_SETTINGS_FILE_NAME)):
        if not args.reset_config:
            msg = ('Target directory is already initialized. '
                   'Use the "-r" flag to force '
                   'reinitialization (might overwrite '
                   'provider configuration files if exist).')
            if is_verbose_output:
                raise CosmoCliError(msg)
            else:
                lgr.error(msg)
                raise
        else:  # resetting provider configuration
            _init_provider(provider, target_directory, args.reset_config,
                           is_verbose_output)
            lgr.info("Configuration reset complete")
            return

    lgr.info("Initializing Cloudify")
    provider_module_name = _init_provider(provider, target_directory,
                                          args.reset_config, is_verbose_output)

    #creating .cloudify file
    _dump_cosmo_working_dir_settings(CosmoWorkingDirectorySettings(),
                                     target_directory)
    with _update_wd_settings(args.verbosity) as wd_settings:
        wd_settings.set_provider(provider_module_name)
    lgr.info("Initialization complete")


def _bootstrap_cosmo(args):
    provider_name = _get_provider(args.verbosity)
    lgr.info("bootstrapping using {0}".format(provider_name))

    provider = _get_provider_module(provider_name, args.verbosity)

    with _protected_provider_call(args.verbosity):
        mgmt_ip = provider.bootstrap(args.config_file_path,
                                     args.verbosity,
                                     args.bootstrap_using_script)

    mgmt_ip = mgmt_ip.encode('utf-8')

    with _update_wd_settings(args.verbosity) as wd_settings:
        wd_settings.set_management_server(mgmt_ip)
    lgr.info(
        "management server is up at {0} (is now set as the default "
        "management server)".format(mgmt_ip))


def _teardown_cosmo(args):
    is_verbose_output = args.verbosity
    if not args.force:
        msg = ("This action requires additional "
               "confirmation. Add the '-f' or '--force' "
               "flags to your command if you are certain "
               "this command should be executed.")
        if is_verbose_output:
            raise CosmoCliError(msg)
        else:
            lgr.error(msg)
            raise

    mgmt_ip = _get_management_server_ip(args)
    lgr.info("tearing down {0}".format(mgmt_ip))

    provider_name = _get_provider(args.verbosity)
    provider = _get_provider_module(provider_name, args.verbosity)
    with _protected_provider_call(args.verbosity):
        provider.teardown(mgmt_ip, args.verbosity,)

    #cleaning relevant data from working directory settings
    with _update_wd_settings(args.verbosity) as wd_settings:
        if wd_settings.remove_management_server_context(mgmt_ip):
            lgr.info(
                "No longer using management server {0} as the "
                "default management server - run 'cfy use' "
                "command to use a different server as default"
                .format(mgmt_ip))

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
    if is_verbose_output:
        raise CosmoCliError(msg)
    else:
        lgr.error(msg)
        raise


def _get_provider(is_verbose_output=False):
    cosmo_wd_settings = _load_cosmo_working_dir_settings(is_verbose_output)
    if cosmo_wd_settings.get_provider():
        return cosmo_wd_settings.get_provider()
    msg = "Provider is not set in working directory settings"
    if is_verbose_output:
        raise RuntimeError(msg)
    else:
        lgr.error(msg)
        raise


def _status(args):
    management_ip = _get_management_server_ip(args)
    lgr.info(
        'querying management server {0}'.format(management_ip))
    client = _get_rest_client(management_ip)
    try:
        client.list_blueprints()
        lgr.info(
            "REST service at management server {0} is up and running"
            .format(management_ip))
        return True
    except CosmoManagerRestCallError:
        lgr.info(
            "REST service at management server {0} is not responding"
            .format(management_ip))
        return False


def _use_management_server(args):
    if not os.path.exists(CLOUDIFY_WD_SETTINGS_FILE_NAME):
        #Allowing the user to work with an existing management server
        #even if "init" wasn't called prior to this.
        _dump_cosmo_working_dir_settings(CosmoWorkingDirectorySettings())

    with _update_wd_settings(args.verbosity) as wd_settings:
        wd_settings.set_management_server(
            wd_settings.translate_management_alias(args.management_ip))
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
    blueprint_id = args.blueprint_id, management_ip

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
        if is_verbose_output:
            raise CosmoCliError(msg)
        else:
            lgr.error(msg)
            raise

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
    deployment_id = event['context']['deployment_id']
    node_id = None
    if 'node_id' in event['context']:
        node_id = event['context']['node_id']
    level = 'CFY'
    message = event['message']['text']
    if 'cloudify_log' in event['type']:
        level = 'LOG'
        message = '{0}: {1}'.format(event['level'].upper(), message)
    timestamp = event['@timestamp'].split('.')[0]
    if node_id is None:
        return '{0} {1} [{2}] {3}'.format(timestamp,
                                          level,
                                          deployment_id,
                                          message)
    else:
        return '{0} {1} [{2}:{3}] {4}'.format(timestamp,
                                              level,
                                              deployment_id,
                                              node_id,
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

    lgr.info("Executing workflow '{0}' on deployment '{1}' at"
             " management server {2}"
             .format(operation, args.deployment_id, management_ip))

    events_logger = _get_events_logger(args)
    client = _get_rest_client(management_ip)
    execution_id, error = client.execute_deployment(deployment_id,
                                                    operation,
                                                    events_logger)
    if error is None:
        lgr.info("Finished executing workflow '{0}' on deployment"
                 "'{1}'".format(operation, deployment_id))
    else:
        lgr.info("Execution of workflow '{0}' for deployment "
                 "'{1}' failed. "
                 "[error={2}]".format(operation, deployment_id, error))
    lgr.info("* Run 'cfy events --include-logs "
             "--execution-id {0}' for retrieving the "
             "execution's events/logs".format(execution_id))


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
        lgr.info(
            'There are no deployments on the '
            'management server for blueprint {0}'.format(blueprint_id))
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


def _list_deployment_executions(args):
    management_ip = _get_management_server_ip(args)
    client = _get_rest_client(management_ip)
    deployment_id = args.deployment_id
    lgr.info(
        'Querying executions list from management server {0} for '
        'deployment {1}'.format(management_ip, deployment_id))
    executions = client.list_deployment_executions(deployment_id)

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
                '\t{0}\t[deployment_id={1}, blueprint_id={2}]'.format(
                    execution.id,
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
    events = client.get_all_execution_events(args.execution_id,
                                             include_logs=args.include_logs)
    events_logger = _get_events_logger(args)
    events_logger(events)
    lgr.info('\nTotal events: {0}'.format(len(events)))


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
        else:
            old_excepthook(type, value, the_traceback)

    sys.excepthook = new_excepthook


def _load_cosmo_working_dir_settings(is_verbose_output=False):
    try:
        with open('{0}'.format(CLOUDIFY_WD_SETTINGS_FILE_NAME), 'r') as f:
            return yaml.safe_load(f.read())
    except IOError:
        msg = ('You must first initialize by running the '
               'command "cfy init", or choose to work with '
               'an existing management server by running the '
               'command "cfy use".')
        if is_verbose_output:
            raise CosmoCliError(msg)
        else:
            lgr.error(msg)
            raise


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
    mapping = resources + "org/cloudifysource/cosmo/dsl/alias-mappings.yaml"

    lgr.info(
        messages.VALIDATING_BLUEPRINT.format(target_file.name))
    try:
        parse_from_path(target_file.name, None, mapping, resources)
    except DSLParsingException as ex:
        msg = (messages.VALIDATING_BLUEPRINT_FAILED
               .format(target_file, str(ex)))
        if is_verbose_output:
            raise CosmoCliError(msg)
        else:
            lgr.error(msg)
            raise
    lgr.info(messages.VALIDATING_BLUEPRINT_SUCCEEDED)


def _get_resource_base():
    script_directory = os.path.dirname(os.path.realpath(__file__))
    resource_directory = script_directory \
        + "/../../cosmo-manager/orchestrator" \
        "/src/main/resources/"
    if os.path.isdir(resource_directory):
        lgr.debug("Found resource directory")

        resource_directory_url = urlparse.urljoin('file:', urllib.pathname2url(
            resource_directory))
        return resource_directory_url
    lgr.debug("Using resources from github. Branch is develop")
    return "https://raw.github.com/CloudifySource/cosmo-manager/develop/" \
           "orchestrator/src/main/resources/"


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
        if is_verbose_output:
            raise CosmoCliError(msg), None, trace
        else:
            lgr.error(msg)
            raise


class CosmoWorkingDirectorySettings(yaml.YAMLObject):
    yaml_tag = u'!WD_Settings'
    yaml_loader = yaml.SafeLoader

    def __init__(self):
        self._management_ip = None
        self._provider = None
        self._mgmt_aliases = {}
        self._mgmt_to_contextual_aliases = {}

    def get_management_server(self):
        return self._management_ip

    def set_management_server(self, management_ip):
        self._management_ip = management_ip

    def remove_management_server_context(self, management_ip):
        # Clears management server context data.
        # Returns True if the management server was the management
        #   server being used at the time of the call
        if management_ip in self._mgmt_to_contextual_aliases:
            del(self._mgmt_to_contextual_aliases[management_ip])
        if self._management_ip == management_ip:
            self._management_ip = None
            return True
        return False

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
            if is_verbose_output:
                raise CosmoCliError(msg)
            else:
                lgr.error(msg)
                raise
        self._mgmt_aliases[management_alias] = management_address


class CosmoCliError(Exception):
    pass

if __name__ == '__main__':
    _set_cli_except_hook()  # only enable hook when this is called directly.
    main()
