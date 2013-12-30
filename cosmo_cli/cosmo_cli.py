#!/usr/bin/env python
# vim: ts=4 sw=4 et
__author__ = 'ran'

# Standard
import argparse
import imp
import sys
import os
import logging
from copy import deepcopy
import yaml


# Project
from cosmo_manager_rest_client.cosmo_manager_rest_client import CosmoManagerRestClient
from cosmo_manager_rest_client.cosmo_manager_rest_client import CosmoManagerRestCallError


CONFIG_FILE_NAME = 'cloudify-config.yaml'
DEFAULTS_CONFIG_FILE_NAME = 'cloudify-config.defaults.yaml'


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger = logging.getLogger(__name__)

    _set_cli_except_hook(logger)

    # http://stackoverflow.com/questions/8144545/turning-off-logging-in-paramiko
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)

    #main parser
    parser = argparse.ArgumentParser(description='Installs Cosmo in an OpenStack environment')

    subparsers = parser.add_subparsers()
    parser_status = subparsers.add_parser('status', help='command for showing general status')
    parser_use = subparsers.add_parser('use', help='command for using a given management server')
    parser_init = subparsers.add_parser('init', help='command for initializing configuration files for installation')
    parser_bootstrap = subparsers.add_parser('bootstrap', help='commands for bootstrapping cloudify')
    parser_blueprints = subparsers.add_parser('blueprints', help='commands for blueprints')
    parser_deployments = subparsers.add_parser('deployments', help='command for deployments')

    #status subparser
    parser_status.set_defaults(handler=_status)

    #use subparser
    parser_use.add_argument(
        'ip',
        metavar='IP',
        type=str,
        help='The cloudify management server ip address'
    )
    parser_use.set_defaults(handler=_use_to_management_server)

    #init subparser
    parser_init.add_argument(
        'provider',
        metavar='PROVIDER',
        type=str,
        help='command for initializing configuration files for a specific provider'
    )
    parser_init.add_argument(
        '-t, --config-target-dir',
        dest='config_target_dir',
        metavar='CONFIG_TARGET_DIRECTORY',
        type=str,
        default=os.getcwd(),
        help='the target directory for the template configuration files'
    )
    parser_init.set_defaults(handler=_init_cosmo_provider)

    #bootstrap subparser
    parser_bootstrap.add_argument(
        'config_file',
        metavar='CONFIG_FILE',
        type=argparse.FileType(),
        help='Path to the cosmo configuration file'
    )
    parser_bootstrap.add_argument(
        '-d, --defaults-config-file',
        dest='defaults_config_file',
        metavar='DEFAULTS_CONFIG_FILE',
        type=argparse.FileType(),
        help='Path to the cosmo defaults configuration file'
    )
    parser_bootstrap.add_argument(
        '-t, --management-ip',
        dest='management_ip',
        metavar='MANAGEMENT_IP',
        type=str,
        help='Existing machine which should cosmo management should be installed and deployed on'
    )
    parser_bootstrap.set_defaults(handler=_bootstrap_cosmo)

    #blueprints subparser
    blueprints_subparsers = parser_blueprints.add_subparsers()
    parser_blueprints_upload = blueprints_subparsers.add_parser('upload',
                                                                help='command for uploading a blueprint to the '
                                                                     'management server')
    parser_blueprints_list = blueprints_subparsers.add_parser('list', help='command for listing all uploaded '
                                                                           'blueprints')
    parser_blueprints_delete = blueprints_subparsers.add_parser('delete', help='command for deleting an uploaded '
                                                                               'blueprint')

    parser_blueprints_upload.add_argument(
        'blueprint_path',
        metavar='BLUEPRINT_FILE',
        type=str,
        help="Path to the application's blueprint file"
    )
    _add_alias_optional_argument_to_parser(parser_blueprints_upload, 'blueprint')
    _add_management_ip_optional_argument_to_parser(parser_blueprints_upload)
    parser_blueprints_upload.set_defaults(handler=_upload_blueprint)

    _add_management_ip_optional_argument_to_parser(parser_blueprints_list)
    parser_blueprints_list.set_defaults(handler=_list_blueprints)

    parser_blueprints_delete.add_argument(
        'blueprint_id',
        metavar='BLUEPRINT_ID',
        type=str,
        help="the id or alias of the blueprint meant for deletion"
    )
    _add_management_ip_optional_argument_to_parser(parser_blueprints_delete)
    parser_blueprints_delete.set_defaults(handler=_delete_blueprint)

    #deployments subparser
    deployments_subparsers = parser_deployments.add_subparsers()
    parser_deployments_create = deployments_subparsers.add_parser('create', help='command for creating a deployment '
                                                                                 'for a blueprint')
    parser_deployments_execute = deployments_subparsers.add_parser('execute', help='command for executing a '
                                                                                   'deployment of a blueprint')

    parser_deployments_execute.add_argument(
        'operation',
        metavar='OPERATION',
        type=str,
        help='The operation to execute'
    )
    parser_deployments_execute.add_argument(
        'deployment_id',
        metavar='DEPLOYMENT_ID',
        type=str,
        help='The id of the deployment to execute the operation on'
    )
    _add_management_ip_optional_argument_to_parser(parser_deployments_execute)
    parser_deployments_execute.set_defaults(handler=_execute_deployment_operation)

    parser_deployments_create.add_argument(
        'blueprint_id',
        metavar='BLUEPRINT_ID',
        type=str,
        help="the id or alias of the blueprint meant for deployment"
    )
    _add_alias_optional_argument_to_parser(parser_deployments_create, 'deployment')
    _add_management_ip_optional_argument_to_parser(parser_deployments_create)
    parser_deployments_create.set_defaults(handler=_create_deployment)

    args = parser.parse_args()
    args.handler(logger, args)


def _get_provider_module(provider_name):
    module_or_pkg_desc = imp.find_module(provider_name)
    if not module_or_pkg_desc[1]:
        #module_or_pkg_desc[1] is the pathname of found module/package, if it's empty none were found
        raise CosmoCliError('Provider not found.')

    module = imp.load_module(provider_name, *module_or_pkg_desc)

    if not module_or_pkg_desc[0]:
        #module_or_pkg_desc[0] is None and module_or_pkg_desc[1] is not empty only when we've loaded a package rather
        #than a module. Re-searching for the module inside the now-loaded package with the same name.
        module = imp.load_module(provider_name, *imp.find_module(provider_name, module.__path__))
    return module


def _load_cosmo_working_dir_settings():
    try:
        with open('.cloudify', 'r') as f:
            return yaml.safe_load(f.read())
    except IOError:
        raise CosmoCliError('You must first initialize using "cosmo init <PROVIDER>"')


def _dump_cosmo_working_dir_settings(cosmo_wd_settings, target_dir=None):
    target_file_path = '.cloudify' if not target_dir else '{0}/.cosmo'.format(target_dir)
    with open(target_file_path, 'w') as f:
        f.write(yaml.dump(cosmo_wd_settings))


def _add_management_ip_optional_argument_to_parser(parser):
    parser.add_argument(
        '-t', '--management-ip',
        dest='management_ip',
        metavar='MANAGEMENT_IP',
        type=str,
        help='The cloudify management server ip address'
    )


def _add_alias_optional_argument_to_parser(parser, object_name):
    parser.add_argument(
        '-a', '--alias',
        dest='alias',
        metavar='ALIAS',
        type=str,
        help='An alias for the {0}'.format(object_name)
    )


def _init_cosmo_provider(logger, args):
    config_target_directory = args.config_target_dir
    #creating .cloudify file
    _dump_cosmo_working_dir_settings(CosmoWorkingDirectorySettings(), config_target_directory)

    try:
        #searching first for the standard name for providers (i.e. cloudify_XXX)
        provider_module = _get_provider_module('cloudify_{0}'.format(args.provider))
    except CosmoCliError:
        #if provider was not found, search for the exact literal the user requested instead
        provider_module = _get_provider_module(args.provider)

    provider_module.init(logger, config_target_directory, CONFIG_FILE_NAME, DEFAULTS_CONFIG_FILE_NAME)


def _bootstrap_cosmo(logger, args):
    defaults_config_file = args.defaults_config_file if args.defaults_config_file else open(
        DEFAULTS_CONFIG_FILE_NAME, 'r')
    config = _read_config(args.config_file, defaults_config_file)

    mgmt_ip = _get_provider_module(args.provider).bootstrap(logger, config, CONFIG_FILE_NAME, DEFAULTS_CONFIG_FILE_NAME)
    logger.info("Management server is up at {0}".format(mgmt_ip))


def _read_config(user_config_file, defaults_config_file):
    try:
        user_config = yaml.safe_load(user_config_file.read())
        defaults_config = yaml.safe_load(defaults_config_file.read())
    finally:
        user_config_file.close()
        defaults_config_file.close()

    merged_config = _deep_merge_dictionaries(user_config, defaults_config)
    return merged_config


def _deep_merge_dictionaries(overriding_dict, overridden_dict):
    merged_dict = deepcopy(overridden_dict)
    for k, v in overriding_dict.iteritems():
        if k in merged_dict and isinstance(v, dict):
            if isinstance(merged_dict[k], dict):
                merged_dict[k] = _deep_merge_dictionaries(v, merged_dict[k])
            else:
                raise RuntimeError('type conflict at key {0}'.format(k))
        else:
            merged_dict[k] = deepcopy(v)
    return merged_dict


def _get_management_server_ip(args):
    if args.management_ip:
        return args.management_ip
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    if cosmo_wd_settings.management_ip:
        return cosmo_wd_settings.management_ip
    raise CosmoCliError("Must either first run 'use' command for a management server or provide a management server "
                        "ip explicitly")


def _translate_blueprint_alias(blueprint_id_or_alias):
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    if blueprint_id_or_alias in cosmo_wd_settings.blueprint_alias_mappings:
        return cosmo_wd_settings.blueprint_alias_mappings[blueprint_id_or_alias]
    return blueprint_id_or_alias


def _translate_deployment_alias(deployment_id_or_alias):
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    if deployment_id_or_alias in cosmo_wd_settings.deployment_alias_mappings:
        return cosmo_wd_settings.deployment_alias_mappings[deployment_id_or_alias]
    return deployment_id_or_alias


def _save_blueprint_alias(blueprint_alias, blueprint_id):
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    if blueprint_alias in cosmo_wd_settings.blueprint_alias_mappings:
        raise CosmoCliError('Blueprint alias {0} is already in use'.format(blueprint_alias))
    cosmo_wd_settings.blueprint_alias_mappings[blueprint_alias] = blueprint_id
    _dump_cosmo_working_dir_settings(cosmo_wd_settings)


def _save_deployment_alias(deployment_alias, deployment_id):
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    if deployment_alias in cosmo_wd_settings.deployment_alias_mappings:
        raise CosmoCliError('Deployment alias {0} is already in use'.format(deployment_alias))
    cosmo_wd_settings.deployment_alias_mappings[deployment_alias] = deployment_id
    _dump_cosmo_working_dir_settings(cosmo_wd_settings)


def _status(logger, args):
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    management_ip = cosmo_wd_settings.management_ip
    logger.info('querying management server {0}'.format(management_ip))
    client = CosmoManagerRestClient(management_ip)
    try:
        client.list_blueprints()
        logger.info("management server {0}'s REST service is up and running".format(management_ip))
    except CosmoManagerRestCallError:
        logger.info("management server {0}'s REST service is not responding".format(management_ip))


def _use_to_management_server(logger, args):
    cosmo_wd_settings = _load_cosmo_working_dir_settings()
    cosmo_wd_settings.management_ip = args.management_ip
    _dump_cosmo_working_dir_settings(cosmo_wd_settings)
    logger.info('Bound to management server {0}'.format(args.management_ip))


def _list_blueprints(logger, args):
    management_ip = _get_management_server_ip(args)
    logger.info('querying blueprints list from management server {0}'.format(management_ip))
    client = CosmoManagerRestClient(management_ip)
    logger.info(client.list_blueprints())


def _delete_blueprint(logger, args):
    blueprint_id = _translate_blueprint_alias(args.blueprint_id)
    management_ip = _get_management_server_ip(args)

    logger.info('Deleting blueprint {0} from management server {1}'.format(args.blueprint_id, management_ip))
    client = CosmoManagerRestClient(management_ip)
    blueprint_state = client.delete_blueprint(blueprint_id)
    logger.info("Deleted blueprint successfully")


def _upload_blueprint(logger, args):
    blueprint_path = args.blueprint_path
    management_ip = _get_management_server_ip(args)
    blueprint_alias = args.alias
    if blueprint_alias and _translate_blueprint_alias(blueprint_alias) != blueprint_alias:
        raise CosmoCliError('Blueprint alias {0} is already in use'.format(blueprint_alias))

    logger.info('Uploading blueprint {0} to management server {1}'.format(blueprint_path, management_ip))
    client = CosmoManagerRestClient(management_ip)
    blueprint_state = client.publish_blueprint(blueprint_path)

    if not blueprint_alias:
        logger.info("Uploaded blueprint, blueprint's id is: {0}".format(blueprint_state.id))
    else:
        _save_blueprint_alias(blueprint_alias, blueprint_state.id)
        logger.info("Uploaded blueprint, blueprint's alias is: {0} (id: {1})".format(blueprint_alias,
                                                                                     blueprint_state.id))


def _create_deployment(logger, args):
    blueprint_id = args.blueprint_id
    translated_blueprint_id = _translate_blueprint_alias(blueprint_id)
    management_ip = _get_management_server_ip(args)
    deployment_alias = args.alias
    if deployment_alias and _translate_deployment_alias(deployment_alias) != deployment_alias:
        raise CosmoCliError('Deployment alias {0} is already in use'.format(deployment_alias))

    logger.info('Creating new deployment from blueprint {0} at management server {1}'.format(blueprint_id,
                                                                                             management_ip))
    client = CosmoManagerRestClient(management_ip)
    deployment = client.create_deployment(translated_blueprint_id)
    if not deployment_alias:
        logger.info("Deployment created, deployment's id is: {0}".format(deployment.id))
    else:
        _save_deployment_alias(deployment_alias, deployment.id)
        logger.info("Deployment created, deployment's alias is: {0} (id: {1})".format(deployment_alias, deployment.id))


def _execute_deployment_operation(logger, args):
    deployment_id = _translate_deployment_alias(args.deployment_id)
    operation = args.operation
    management_ip = _get_management_server_ip(args)

    logger.info('Executing operation {0} on deployment {1} at management server {2}'
                .format(operation, args.deployment_id, management_ip))

    def events_logger(events):
        for event in events:
            logger.info(event)

    client = CosmoManagerRestClient(management_ip)
    client.execute_deployment(deployment_id, operation, events_logger)
    logger.info("Finished executing operation {0} on deployment".format(operation))


def _set_cli_except_hook(logger):
    old_excepthook = sys.excepthook

    def new_excepthook(type, value, the_traceback):
        if type == CosmoCliError:
            logger.error(value.message)
        elif type == CosmoManagerRestCallError:
            logger.error("Failed making a call to REST service: {0}".format(value.message))
        else:
            old_excepthook(type, value, the_traceback)

    sys.excepthook = new_excepthook


class CosmoWorkingDirectorySettings(yaml.YAMLObject):
    yaml_tag = u'!WD_Settings'
    yaml_loader = yaml.SafeLoader

    def __init__(self, management_ip=None, blueprint_alias_mappings=None, deployment_alias_mappings=None):
        self.management_ip = management_ip
        self.blueprint_alias_mappings = blueprint_alias_mappings if blueprint_alias_mappings else {}
        self.deployment_alias_mappings = deployment_alias_mappings if deployment_alias_mappings else {}


class CosmoCliError(Exception):
    pass

if __name__ == '__main__':
    main()