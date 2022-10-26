########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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
import json
import shutil
from urllib.parse import urlparse

import click

from dsl_parser.parser import parse_from_path
from dsl_parser.exceptions import DSLParsingException
from cloudify_rest_client.constants import VISIBILITY_EXCEPT_PRIVATE

from cloudify_cli import (
    blueprint,
    env,
    exceptions,
    filters_utils,
    local,
    utils)
from cloudify_cli.cli import cfy, helptexts
from cloudify_cli.config import config
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.labels_utils import (
    add_labels,
    delete_labels,
    list_labels,
    serialize_resource_labels)
from cloudify_cli.logger import get_global_json_output
from cloudify_cli.table import print_data, print_single
from cloudify_cli.utils import (
    prettify_client_error,
    get_visibility,
    validate_visibility)
from cloudify_cli.commands.summary import (
    BASE_SUMMARY_FIELDS,
    structure_summary_results)


DESCRIPTION_LIMIT = 20
BASE_BLUEPRINT_COLUMNS = ['id', 'description', 'main_file_name', 'created_at']
BLUEPRINT_COLUMNS = BASE_BLUEPRINT_COLUMNS + ['updated_at', 'visibility',
                                              'tenant_name', 'created_by',
                                              'state', 'error', 'labels']
INPUTS_COLUMNS = ['name', 'type', 'default', 'description']
BLUEPRINTS_SUMMARY_FIELDS = BASE_SUMMARY_FIELDS


@cfy.group(name='blueprints')
@cfy.options.common_options
def blueprints():
    """Handle blueprints on the manager"""


@blueprints.command(name='upload',
                    short_help='Upload a blueprint [manager only]')
@cfy.argument('blueprint-path')
@cfy.options.blueprint_id(validate=True)
@cfy.options.blueprint_filename()
@cfy.options.blueprint_icon_path()
@cfy.options.async_upload
@cfy.options.labels
@cfy.options.validate
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.options.private_resource
@cfy.options.visibility()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.pass_context
def upload(ctx,
           blueprint_path,
           blueprint_id,
           blueprint_filename,
           icon_path,
           async_upload,
           labels,
           validate,
           private_resource,
           visibility,
           logger,
           client,
           tenant_name):
    """Upload a blueprint to the manager

    `BLUEPRINT_PATH` can be either a local blueprint yaml file or
    blueprint archive; a url to a blueprint archive or an
    `organization/blueprint_repo[:tag/branch]` (to be
    retrieved from GitHub).
    Supported archive types are: zip, tar, tar.gz and tar.bz2
    """
    if client.manager.get_version().get('edition') == 'premium':
        client.license.check()
    utils.explicit_tenant_name_message(tenant_name, logger)
    processed_blueprint_path = blueprint.get(
        blueprint_path, blueprint_filename, icon_path)

    # Take into account that `blueprint.get` might not return a URL
    # instead of a blueprint file (archive files are not locally downloaded)
    parsed_path = urlparse(processed_blueprint_path)
    is_url = bool(
        parsed_path.scheme
        # But on windows there will always be a scheme, so check if the path
        # exists
        and not os.path.exists(processed_blueprint_path)
    )

    progress_handler = utils.generate_progress_handler(blueprint_path, '')
    blueprint_id = blueprint_id or blueprint.generate_id(
        processed_blueprint_path, blueprint_filename)
    visibility = get_visibility(private_resource, visibility, logger)

    if is_url:
        # When a URL is passed it's assumed to be pointing to an archive
        # file that contains the blueprint. Hence, the `publish_archive`
        # API call is the one that should be used.
        logger.info('Publishing blueprint archive %s...',
                    processed_blueprint_path)
        client.blueprints.publish_archive(
            processed_blueprint_path,
            blueprint_id,
            blueprint_filename,
            visibility,
            progress_handler,
            async_upload=True,
            labels=labels
        )
        if icon_path:
            client.blueprints.upload_icon(blueprint_id, icon_path)
    else:
        try:
            if validate:
                ctx.invoke(
                    validate_blueprint,
                    blueprint_path=processed_blueprint_path,
                )

            # When the blueprint file is already available locally, it can be
            # uploaded directly using the `upload` API call.
            logger.info('Uploading blueprint %s...', blueprint_path)
            client.blueprints.upload(
                processed_blueprint_path,
                blueprint_id,
                visibility,
                progress_handler,
                # if blueprint is in an archive we skip the size limit check
                utils.is_archive(blueprint_path),
                async_upload=True,
                labels=labels
            )
        finally:
            # When an archive file is passed, it's extracted to a temporary
            # directory to get the blueprint file. Once the blueprint has been
            # uploaded, the temporary directory needs to be cleaned up.
            if processed_blueprint_path != blueprint_path:
                temp_directory = os.path.dirname(
                    os.path.dirname(processed_blueprint_path)
                )
                shutil.rmtree(temp_directory)

    logger.info("Blueprint `{0}` upload started.".format(blueprint_id))

    if not async_upload:
        blueprint_obj = utils.wait_for_blueprint_upload(client,
                                                        blueprint_id,
                                                        logger.level)
        logger.info("Blueprint uploaded. The blueprint's id is {0}".format(
            blueprint_obj.id))


@blueprints.command(name='download',
                    short_help='Download a blueprint [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.output_path
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def download(blueprint_id, output_path, logger, client, tenant_name):
    """Download a blueprint from the manager

    `BLUEPRINT_ID` is the id of the blueprint to download.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Downloading blueprint {0}...'.format(blueprint_id))
    blueprint_name = output_path if output_path else blueprint_id
    progress_handler = utils.generate_progress_handler(blueprint_name, '')
    target_file = client.blueprints.download(blueprint_id,
                                             output_path,
                                             progress_handler)
    logger.info('Blueprint downloaded as {0}'.format(target_file))


@blueprints.command(name='delete',
                    short_help='Delete a blueprint [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.force(help=helptexts.FORCE_DELETE_BLUEPRINT)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete(blueprint_id, force, logger, client, tenant_name):
    """Delete a blueprint from the manager

    `BLUEPRINT_ID` is the id of the blueprint to delete.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Deleting blueprint {0}...'.format(blueprint_id))
    client.blueprints.delete(blueprint_id, force)
    logger.info('Blueprint deleted')


@blueprints.command(name='list', short_help='List blueprints')
@cfy.options.filter_id
@cfy.options.blueprint_filter_rules
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.common_options
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='blueprint')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def manager_list(filter_id,
                 filter_rules,
                 sort_by,
                 descending,
                 tenant_name,
                 all_tenants,
                 search,
                 pagination_offset,
                 pagination_size,
                 logger,
                 client):
    """List all blueprints
    """
    def trim_description(blueprint):
        if blueprint['description'] is not None:
            if len(blueprint['description']) >= DESCRIPTION_LIMIT:
                blueprint['description'] = '{0}..'.format(
                    blueprint['description'][:DESCRIPTION_LIMIT - 2])
        else:
            blueprint['description'] = ''
        return blueprint

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing all blueprints...')

    blueprints_list = client.blueprints.list(
        sort=sort_by,
        is_descending=descending,
        _all_tenants=all_tenants,
        _search=search,
        _offset=pagination_offset,
        _size=pagination_size,
        filter_rules=filter_rules,
        filter_id=filter_id
    )
    blueprints = [trim_description(b) for b in blueprints_list]
    serialize_resource_labels(blueprints)
    print_data(BLUEPRINT_COLUMNS, blueprints, 'Blueprints:')

    total = blueprints_list.metadata.pagination.total
    base_str = 'Showing {0} of {1} blueprints'.format(
        len(blueprints_list), total)
    if filter_rules or filter_id:
        filtered = blueprints_list.metadata.get('filtered')
        if filtered is not None:
            base_str += ' ({} hidden by filter)'.format(filtered)
    logger.info(base_str)


@blueprints.command(name='get',
                    short_help='Retrieve blueprint information [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def get(blueprint_id, logger, client, tenant_name):
    """Retrieve information for a specific blueprint

    `BLUEPRINT_ID` is the id of the blueprint to get information on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving blueprint {0}...'.format(blueprint_id))
    blueprint_dict = client.blueprints.get(blueprint_id)
    deployments = client.deployments.list(_include=['id'],
                                          blueprint_id=blueprint_id)
    blueprint_dict['#deployments'] = len(deployments)
    columns = BLUEPRINT_COLUMNS + ['#deployments']
    blueprint_metadata = blueprint_dict['plan']['metadata'] or {}
    blueprint_plugins = {k: [p for p in blueprint_dict['plan'][k]
                             if p['package_name'] and p['package_version']]
                         for k in ['deployment_plugins_to_install',
                                   'workflow_plugins_to_install',
                                   'host_agent_plugins_to_install']
                         if k in blueprint_dict['plan']
                         and blueprint_dict['plan'][k]}
    blueprint_deployments = [d['id'] for d in deployments]

    if get_global_json_output():
        columns += ['description', 'metadata', 'deployments',
                    'error_traceback']
        blueprint_dict['metadata'] = blueprint_metadata
        blueprint_dict['deployments'] = blueprint_deployments
        print_single(columns, blueprint_dict, 'Blueprint:', max_width=50)
    else:
        serialize_resource_labels([blueprint_dict])
        print_single(columns, blueprint_dict, 'Blueprint:', max_width=50)

        logger.info('Description:')
        logger.info('{0}\n'.format(blueprint_dict['description'] or ''))

        if blueprint_metadata:
            logger.info('Metadata:')
            for property_name, property_value in \
                    blueprint_dict['plan']['metadata'].items():
                logger.info('\t{0}: {1}'.format(property_name, property_value))
            logger.info('')

        if blueprint_plugins:
            plugins_dict = {}
            for plugin_key, plugins in blueprint_plugins.items():
                plugin_purpose = plugin_key.partition('_')[0]
                for plugin in plugins:
                    plugin_id = '{0}=={1}'.format(plugin['package_name'],
                                                  plugin['package_version'])
                    if plugin_id in plugins_dict:
                        plugins_dict[plugin_id].append(plugin_purpose)
                    else:
                        plugins_dict[plugin_id] = [plugin_purpose]
            logger.info('Plugins:')
            for plugin, plugin_purpose in plugins_dict.items():
                logger.info('\t{0} ({1})'.format(plugin,
                                                 ', '.join(plugin_purpose)))
            logger.info('')

        logger.info('Existing deployments:')
        logger.info('{0}\n'.format(json.dumps(blueprint_deployments)))


@blueprints.command(name='inputs',
                    short_help='Retrieve blueprint inputs [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def inputs(blueprint_id, logger, client, tenant_name):
    """Retrieve inputs for a specific blueprint

    `BLUEPRINT_ID` is the path of the blueprint to get inputs for.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving inputs for blueprint {0}...'.format(blueprint_id))
    blueprint_dict = client.blueprints.get(blueprint_id)
    inputs = blueprint_dict['plan']['inputs']
    data = [{'name': name,
             'type': input.get('type', '-'),
             'default': input.get('default', '-'),
             'description': input.get('description', '-')}
            for name, input in inputs.items()]

    print_data(INPUTS_COLUMNS, data, 'Inputs:')


@blueprints.command(name='package',
                    short_help='Create a blueprint archive')
@cfy.argument('blueprint-path')
@cfy.options.optional_output_path
@cfy.options.validate
@cfy.options.common_options
@cfy.pass_logger
@cfy.pass_context
def package(ctx, blueprint_path, output_path, validate, logger):
    """Create a blueprint archive

    `BLUEPRINT_PATH` is either the path to the blueprint yaml itself or
    to the directory in which the blueprint yaml files resides.
    """
    blueprint_path = os.path.abspath(blueprint_path)
    destination = output_path or blueprint.generate_id(blueprint_path)

    if validate:
        ctx.invoke(validate_blueprint, blueprint_path=blueprint_path)
    logger.info('Creating blueprint archive {0}...'.format(destination))
    if os.path.isdir(blueprint_path):
        path_to_package = blueprint_path
    elif os.path.isfile(blueprint_path):
        path_to_package = os.path.dirname(blueprint_path)
    else:
        raise CloudifyCliError(
            "You must provide a path to a blueprint's directory or to a "
            "blueprint yaml file residing in a blueprint's directory.")
    if os.name == 'nt':
        utils.create_zip(path_to_package, destination + '.zip')
    else:
        utils.tar(path_to_package, destination + '.tar.gz')
    logger.info('Packaging complete!')


@blueprints.command(name='create-requirements',
                    short_help='Create pip-requirements')
@cfy.argument('blueprint-path', type=click.Path(exists=True))
@cfy.options.optional_output_path
@cfy.options.common_options
@cfy.pass_logger
def create_requirements(blueprint_path, output_path, logger):
    """Generate a pip-compliant requirements file for a given blueprint

    `BLUEPRINT_PATH` is the path to the blueprint for which the file
    will be generated.
    """
    if output_path and os.path.exists(output_path):
        raise exceptions.CloudifyCliError(
            'Path {0} already exists'.format(output_path))

    requirements = local.create_requirements(blueprint_path=blueprint_path)

    if output_path:
        utils.dump_to_file(requirements, output_path)
        logger.info('Requirements file created successfully --> {0}'
                    .format(output_path))
    else:
        for requirement in requirements:
            logger.info(requirement)


@blueprints.command(name='set-global',
                    short_help="Set the blueprint's visibility to global")
@cfy.argument('blueprint-id')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_global(blueprint_id, logger, client):
    """Set the blueprint's visibility to global

    `BLUEPRINT_ID` is the id of the blueprint to set global
    """
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        client.blueprints.set_global(blueprint_id)
        logger.info('Blueprint `{0}` was set to global'.format(blueprint_id))
        logger.warning("This command is deprecated and will be removed soon, "
                       "please use the 'set-visibility' command instead")


@blueprints.command(name='set-visibility',
                    short_help="Set the blueprint's visibility")
@cfy.argument('blueprint-id')
@cfy.options.visibility(required=True, valid_values=VISIBILITY_EXCEPT_PRIVATE)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_visibility(blueprint_id, visibility, logger, client):
    """Set the blueprint's visibility

    `BLUEPRINT_ID` is the id of the blueprint to update
    """
    validate_visibility(visibility, valid_values=VISIBILITY_EXCEPT_PRIVATE)
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        client.blueprints.set_visibility(blueprint_id, visibility)
        logger.info('Blueprint `{0}` was set to {1}'.format(blueprint_id,
                                                            visibility))


@blueprints.command(name='summary',
                    short_help='Retrieve summary of blueprint details '
                               '[manager only]',
                    help=helptexts.SUMMARY_HELP.format(
                        type='blueprints',
                        example='blueprint with the same tenant name',
                        fields='|'.join(BLUEPRINTS_SUMMARY_FIELDS)))
@cfy.argument('target_field', type=cfy.SummaryArgs(BLUEPRINTS_SUMMARY_FIELDS))
@cfy.argument('sub_field', type=cfy.SummaryArgs(BLUEPRINTS_SUMMARY_FIELDS),
              default=None, required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def summary(target_field, sub_field, logger, client, tenant_name,
            all_tenants):
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of blueprints on field {field}'.format(
        field=target_field))

    summary = client.summary.blueprints.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
    )

    columns, items = structure_summary_results(
        summary.items,
        target_field,
        sub_field,
        'blueprints',
    )

    print_data(
        columns,
        items,
        'Blueprint summary by {field}'.format(field=target_field),
    )


@blueprints.command(name='set-icon',
                    short_help="Set or remove blueprint's icon")
@cfy.argument('blueprint-id')
@cfy.options.blueprint_icon_path()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def set_icon(blueprint_id, icon_path, logger, client):
    """Set an icon which will be used to describe/identify the blueprint.
    In case `-i [ICON_PATH]` is provided, the [ICON_PATH] should point to
    a valid PNG image. If this parameter is omitted, the icon will be removed
    from the blueprint's resources.
    """
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        if icon_path:
            client.blueprints.upload_icon(blueprint_id, icon_path)
            logger.info('Blueprint `{0}` has a new icon set.'
                        .format(blueprint_id))
        else:
            client.blueprints.remove_icon(blueprint_id)
            logger.info('Blueprint `{0}` has its icon removed.'
                        .format(blueprint_id))


@blueprints.command(name='set-owner',
                    short_help="Change blueprint's ownership")
@cfy.argument('blueprint-id')
@cfy.options.new_username()
@cfy.options.tenant_name(required=False, resource_name_for_help='secret')
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def set_owner(blueprint_id, username, tenant_name, logger, client):
    """Set a new owner for the blueprint."""
    utils.explicit_tenant_name_message(tenant_name, logger)
    bp = client.blueprints.update(blueprint_id, {'creator': username})
    logger.info('Blueprint `%s` is now owned by user `%s`.',
                blueprint_id, bp.get('created_by'))


@blueprints.group(name='labels',
                  short_help="Handle a blueprint's labels")
@cfy.options.common_options
def labels():
    if not env.is_initialized():
        env.raise_uninitialized()


@labels.command(name='list',
                short_help="List the labels of a specific blueprint")
@cfy.argument('blueprint-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list_blueprint_labels(blueprint_id,
                          logger,
                          client,
                          tenant_name):
    list_labels(blueprint_id, 'blueprint', client.blueprints,
                logger, tenant_name)


@labels.command(name='add',
                short_help="Add labels to a specific blueprint")
@cfy.argument('labels-list',
              callback=cfy.parse_and_validate_labels)
@cfy.argument('blueprint-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_blueprint_labels(labels_list,
                         blueprint_id,
                         logger,
                         client,
                         tenant_name):
    """LABELS_LIST: <key>:<value>,<key>:<value>.
    Any comma and colon in <value> must be escaped with '\\'."""
    add_labels(blueprint_id, 'blueprint', client.blueprints, labels_list,
               logger, tenant_name)


@labels.command(name='delete',
                short_help="Delete labels from a specific blueprint")
@cfy.argument('label', callback=cfy.parse_and_validate_label_to_delete)
@cfy.argument('blueprint-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete_blueprint_labels(label,
                            blueprint_id,
                            logger,
                            client,
                            tenant_name):
    """
    LABEL: A mixed list of labels and keys, i.e.
    <key>:<value>,<key>,<key>:<value>. If <key> is provided,
    all labels associated with this key will be deleted from the deployment.
    Any comma and colon in <value> must be escaped with `\\`
    """
    delete_labels(blueprint_id, 'blueprint', client.blueprints, label,
                  logger, tenant_name)


@blueprints.group(name='filters',
                  short_help="Handle the blueprints' filters")
@cfy.options.common_options
def filters():
    if not env.is_initialized():
        env.raise_uninitialized()


@filters.command(name='list',
                 short_help="List all filters associated with blueprints")
@cfy.options.sort_by('id')
@cfy.options.descending
@cfy.options.common_options
@cfy.options.tenant_name_for_list(required=False,
                                  resource_name_for_help='filter')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list_blueprints_filters(sort_by,
                            descending,
                            tenant_name,
                            all_tenants,
                            search,
                            pagination_offset,
                            pagination_size,
                            logger,
                            client):
    """List all blueprints' filters"""
    filters_utils.list_filters('blueprints',
                               sort_by,
                               descending,
                               tenant_name,
                               all_tenants,
                               search,
                               pagination_offset,
                               pagination_size,
                               logger,
                               client.blueprints_filters)


@filters.command(name='create', short_help="Create a new blueprints' filter")
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.blueprint_filter_rules
@cfy.options.visibility(mutually_exclusive_required=False)
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def create_blueprints_filter(filter_id,
                             filter_rules,
                             visibility,
                             tenant_name,
                             logger,
                             client):
    """Create a new blueprints' filter

    `FILTER-ID` is the new filter's ID
    """
    filters_utils.create_filter('blueprints',
                                filter_id,
                                filter_rules,
                                visibility,
                                tenant_name,
                                logger,
                                client.blueprints_filters)


@filters.command(name='get',
                 short_help="Get details for a single blueprints' filter")
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def get_blueprints_filter(filter_id, tenant_name, logger, client):
    """Get details for a single blueprints' filter

    `FILTER-ID` is the filter's ID
    """
    filters_utils.get_filter('blueprints',
                             filter_id,
                             tenant_name,
                             logger,
                             client.blueprints_filters)


@filters.command(name='update',
                 short_help="Update an existing blueprints' filter")
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.blueprint_filter_rules
@cfy.options.update_visibility
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def update_blueprints_filter(filter_id,
                             filter_rules,
                             visibility,
                             tenant_name,
                             logger,
                             client):
    """Update an existing blueprints' filter's filter rules or visibility

    `FILTER-ID` is the filter's ID
    """
    filters_utils.update_filter('blueprints',
                                filter_id,
                                filter_rules,
                                visibility,
                                tenant_name,
                                logger,
                                client.blueprints_filters)


@filters.command(name='delete', short_help="Delete a blueprints' filter")
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete_deployments_filter(filter_id, tenant_name, logger, client):
    """Delete a blueprints' filter

    `FILTER-ID` is the filter's ID
    """
    filters_utils.delete_filter('blueprints',
                                filter_id,
                                tenant_name,
                                logger,
                                client.blueprints_filters)


@cfy.group(name='blueprints')
@cfy.options.common_options
def local_blueprints():
    """Handle local blueprints"""


@local_blueprints.command(name='list', short_help='List blueprints')
@cfy.options.local_common_options
@cfy.pass_logger
@cfy.options.extended_view
def local_list(logger):
    blueprints = local.list_blueprints()
    print_data(BASE_BLUEPRINT_COLUMNS, blueprints, 'Blueprints:')


@local_blueprints.command(name='install-plugins',
                          short_help='Install plugins [locally]')
@cfy.argument('blueprint-path', type=click.Path(exists=True))
@cfy.options.common_options
@cfy.assert_local_active
@cfy.pass_logger
def install_plugins(blueprint_path, logger):
    """Install the necessary plugins for a given blueprint in the
       local environment.

    Currently only supports passing the YAML of the blueprint directly.

    `BLUEPRINT_PATH` is the path to the blueprint to install plugins for.
    """
    logger.info('Installing plugins...')
    local._install_plugins(blueprint_path=blueprint_path)


@click.command(name='validate', short_help='Validate a blueprint')
@cfy.argument('blueprint-path')
@cfy.options.common_options
@cfy.pass_logger
def validate_blueprint(blueprint_path, logger):
    """Validate a blueprint

    `BLUEPRINT_PATH` is the path of the blueprint to validate.
    """
    logger.info('Validating blueprint: {0}'.format(blueprint_path))
    try:
        resolver = config.get_import_resolver()
        validate_version = config.is_validate_definitions_version()
        parse_from_path(
            dsl_file_path=blueprint_path,
            resolver=resolver,
            validate_version=validate_version)
    except DSLParsingException as ex:
        raise CloudifyCliError('Failed to validate blueprint: {0}'.format(ex))
    logger.info('Blueprint validated successfully')


blueprints.add_command(validate_blueprint)
local_blueprints.add_command(validate_blueprint)
