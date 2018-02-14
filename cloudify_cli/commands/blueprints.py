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
import json
import shutil
from urlparse import urlparse

import click

from dsl_parser.parser import parse_from_path
from dsl_parser.exceptions import DSLParsingException
from cloudify_rest_client.constants import VISIBILITY_EXCEPT_PRIVATE

from .. import local
from .. import utils
from ..cli import cfy
from .. import blueprint
from .. import exceptions
from ..config import config
from ..table import print_data
from ..exceptions import CloudifyCliError
from ..utils import (prettify_client_error,
                     get_visibility,
                     validate_visibility)


DESCRIPTION_LIMIT = 20
BLUEPRINT_COLUMNS = ['id', 'description', 'main_file_name', 'created_at',
                     'updated_at', 'visibility', 'tenant_name', 'created_by']
INPUTS_COLUMNS = ['name', 'type', 'default', 'description']


@cfy.group(name='blueprints')
@cfy.options.verbose()
def blueprints():
    """Handle blueprints on the manager
    """
    pass


@blueprints.command(name='validate',
                    short_help='Validate a blueprint')
@cfy.argument('blueprint-path')
@cfy.options.verbose()
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
        raise CloudifyCliError('Failed to validate blueprint {0}'.format(ex))
    logger.info('Blueprint validated successfully')


@blueprints.command(name='upload',
                    short_help='Upload a blueprint [manager only]')
@cfy.argument('blueprint-path')
@cfy.options.blueprint_id()
@cfy.options.blueprint_filename()
@cfy.options.validate
@cfy.options.verbose()
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
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))

    processed_blueprint_path = blueprint.get(
        blueprint_path, blueprint_filename)

    # Take into account that `blueprint.get` might not return a URL
    # instead of a blueprint file (archive files are not locally downloaded)
    is_url = bool(urlparse(processed_blueprint_path).scheme)

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
        blueprint_obj = client.blueprints.publish_archive(
            processed_blueprint_path,
            blueprint_id,
            blueprint_filename,
            visibility,
            progress_handler)
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
            blueprint_obj = client.blueprints.upload(
                processed_blueprint_path,
                blueprint_id,
                visibility,
                progress_handler
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

    logger.info("Blueprint uploaded. The blueprint's id is {0}".format(
        blueprint_obj.id))


@blueprints.command(name='download',
                    short_help='Download a blueprint [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.output_path
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def download(blueprint_id, output_path, logger, client, tenant_name):
    """Download a blueprint from the manager

    `BLUEPRINT_ID` is the id of the blueprint to download.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
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
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete(blueprint_id, logger, client, tenant_name):
    """Delete a blueprint from the manager

    `BLUEPRINT_ID` is the id of the blueprint to delete.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Deleting blueprint {0}...'.format(blueprint_id))
    client.blueprints.delete(blueprint_id)
    logger.info('Blueprint deleted')


@blueprints.command(name='list',
                    short_help='List blueprints [manager only]')
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.verbose()
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='blueprint')
@cfy.options.all_tenants
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by,
         descending,
         tenant_name,
         all_tenants,
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

    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Listing all blueprints...')
    blueprints_list = client.blueprints.list(
        sort=sort_by,
        is_descending=descending,
        _all_tenants=all_tenants,
        _offset=pagination_offset,
        _size=pagination_size
    )
    blueprints = [trim_description(b) for b in blueprints_list]
    print_data(BLUEPRINT_COLUMNS, blueprints, 'Blueprints:')
    total = blueprints_list.metadata.pagination.total
    logger.info('Showing {0} of {1} blueprints'.format(len(blueprints), total))


@blueprints.command(name='get',
                    short_help='Retrieve blueprint information [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get(blueprint_id, logger, client, tenant_name):
    """Retrieve information for a specific blueprint

    `BLUEPRINT_ID` is the id of the blueprint to get information on.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Retrieving blueprint {0}...'.format(blueprint_id))
    blueprint_dict = client.blueprints.get(blueprint_id)
    deployments = client.deployments.list(_include=['id'],
                                          blueprint_id=blueprint_id)
    blueprint_dict['#deployments'] = len(deployments)
    columns = BLUEPRINT_COLUMNS + ['#deployments']
    print_data(columns, blueprint_dict, 'Blueprint:', max_width=50)

    logger.info('Description:')
    logger.info('{0}\n'.format(blueprint_dict['description'] or ''))

    logger.info('Existing deployments:')
    logger.info('{0}\n'.format(json.dumps([d['id'] for d in deployments])))


@blueprints.command(name='inputs',
                    short_help='Retrieve blueprint inputs [manager only]')
@cfy.argument('blueprint-id')
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='blueprint')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def inputs(blueprint_id, logger, client, tenant_name):
    """Retrieve inputs for a specific blueprint

    `BLUEPRINT_ID` is the path of the blueprint to get inputs for.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Retrieving inputs for blueprint {0}...'.format(blueprint_id))
    blueprint_dict = client.blueprints.get(blueprint_id)
    inputs = blueprint_dict['plan']['inputs']
    data = [{'name': name,
             'type': input.get('type', '-'),
             'default': input.get('default', '-'),
             'description': input.get('description', '-')}
            for name, input in inputs.iteritems()]

    print_data(INPUTS_COLUMNS, data, 'Inputs:')


@blueprints.command(name='package',
                    short_help='Create a blueprint archive')
@cfy.argument('blueprint-path')
@cfy.options.optional_output_path
@cfy.options.validate
@cfy.options.verbose()
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
        utils.zip(path_to_package, destination + '.zip')
    else:
        utils.tar(path_to_package, destination + '.tar.gz')
    logger.info('Packaging complete!')


@blueprints.command(name='create-requirements',
                    short_help='Create pip-requirements')
@cfy.argument('blueprint-path', type=click.Path(exists=True))
@cfy.options.optional_output_path
@cfy.options.verbose()
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


@blueprints.command(name='install-plugins',
                    short_help='Install plugins [locally]')
@cfy.argument('blueprint-path', type=click.Path(exists=True))
@cfy.options.verbose()
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


@blueprints.command(name='set-global',
                    short_help="Set the blueprint's visibility to global")
@cfy.argument('blueprint-id')
@cfy.options.verbose()
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
        logger.info("This command will be deprecated soon, please use the "
                    "'set-visibility' command instead")


@blueprints.command(name='set-visibility',
                    short_help="Set the blueprint's visibility")
@cfy.argument('blueprint-id')
@cfy.options.visibility(required=True, valid_values=VISIBILITY_EXCEPT_PRIVATE)
@cfy.options.verbose()
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
