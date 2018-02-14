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
from StringIO import StringIO

from cloudify_rest_client.exceptions import DeploymentPluginNotFound
from cloudify_rest_client.exceptions import UnknownDeploymentInputError
from cloudify_rest_client.exceptions import UnknownDeploymentSecretError
from cloudify_rest_client.exceptions import MissingRequiredDeploymentInputError
from cloudify_rest_client.exceptions import UnsupportedDeploymentGetSecretError
from cloudify_rest_client.constants import (VisibilityState,
                                            VISIBILITY_EXCEPT_GLOBAL)

from .. import utils
from ..local import load_env
from ..table import print_data
from ..cli import cfy, helptexts
from ..logger import get_events_logger
from .. import execution_events_fetcher
from ..constants import DEFAULT_BLUEPRINT_PATH
from ..exceptions import CloudifyCliError, SuppressedCloudifyCliError
from ..utils import (prettify_client_error,
                     get_visibility,
                     validate_visibility)

DEPLOYMENT_COLUMNS = ['id', 'blueprint_id', 'created_at', 'updated_at',
                      'visibility', 'tenant_name', 'created_by']
TENANT_HELP_MESSAGE = 'The name of the tenant of the deployment'


@cfy.group(name='deployments')
@cfy.options.verbose()
def deployments():
    """Handle deployments on the Manager
    """
    pass


@cfy.command(name='list', short_help='List deployments [manager only]')
@cfy.options.blueprint_id()
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='deployment')
@cfy.options.all_tenants
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_list(blueprint_id,
                 sort_by,
                 descending,
                 all_tenants,
                 pagination_offset,
                 pagination_size,
                 logger,
                 client,
                 tenant_name):
    """List deployments

    If `--blueprint-id` is provided, list deployments for that blueprint.
    Otherwise, list deployments for all blueprints.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    if blueprint_id:
        logger.info('Listing deployments for blueprint {0}...'.format(
            blueprint_id))
    else:
        logger.info('Listing all deployments...')

    deployments = client.deployments.list(sort=sort_by,
                                          is_descending=descending,
                                          _all_tenants=all_tenants,
                                          _offset=pagination_offset,
                                          _size=pagination_size)
    total = deployments.metadata.pagination.total
    if blueprint_id:
        deployments = filter(lambda deployment:
                             deployment['blueprint_id'] == blueprint_id,
                             deployments)
    print_data(DEPLOYMENT_COLUMNS, deployments, 'Deployments:')
    logger.info('Showing {0} of {1} deployments'.format(len(deployments),
                                                        total))


@cfy.command(name='update', short_help='Update a deployment [manager only]')
@cfy.argument('deployment-id')
@cfy.options.blueprint_path(required=True)
@cfy.options.inputs
@cfy.options.blueprint_filename()
@cfy.options.workflow_id('update')
@cfy.options.skip_install
@cfy.options.skip_uninstall
@cfy.options.force(help=helptexts.FORCE_UPDATE)
@cfy.options.include_logs
@cfy.options.json_output
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_update(deployment_id,
                   blueprint_path,
                   inputs,
                   blueprint_filename,
                   skip_install,
                   skip_uninstall,
                   workflow_id,
                   force,
                   include_logs,
                   json_output,
                   logger,
                   client,
                   tenant_name):
    """Update a specified deployment according to the specified blueprint

    `DEPLOYMENT_ID` is the deployment's id to update.
    """
    if not utils.is_archive(blueprint_path) and \
            blueprint_filename not in (DEFAULT_BLUEPRINT_PATH, blueprint_path):
        raise CloudifyCliError(
            '--blueprint-filename param should be passed '
            'only when updating from an archive'
        )

    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    blueprint_or_archive_path = blueprint_path
    logger.info('Updating deployment {0} using blueprint {1}'.format(
        deployment_id, blueprint_or_archive_path))

    deployment_update = client.deployment_updates.update(
        deployment_id,
        blueprint_or_archive_path,
        application_file_name=blueprint_filename,
        inputs=inputs,
        workflow_id=workflow_id,
        skip_install=skip_install,
        skip_uninstall=skip_uninstall,
        force=force)
    events_logger = get_events_logger(json_output)

    execution = execution_events_fetcher.wait_for_execution(
        client,
        client.executions.get(deployment_update.execution_id),
        events_handler=events_logger,
        include_logs=include_logs,
        timeout=None)  # don't timeout ever

    if execution.error:
        logger.info("Execution of workflow '{0}' for deployment "
                    "'{1}' failed. [error={2}]"
                    .format(execution.workflow_id,
                            execution.deployment_id,
                            execution.error))
        logger.info('Failed updating deployment {dep_id}. Deployment update '
                    'id: {depup_id}. Execution id: {exec_id}'
                    .format(depup_id=deployment_update.id,
                            dep_id=deployment_id,
                            exec_id=execution.id))
        raise SuppressedCloudifyCliError()
    else:
        logger.info("Finished executing workflow '{0}' on deployment "
                    "'{1}'".format(execution.workflow_id,
                                   execution.deployment_id))
        logger.info('Successfully updated deployment {dep_id}. '
                    'Deployment update id: {depup_id}. Execution id: {exec_id}'
                    .format(depup_id=deployment_update.id,
                            dep_id=deployment_id,
                            exec_id=execution.id))


@cfy.command(name='create',
             short_help='Create a deployment [manager only]')
@cfy.argument('deployment-id', required=False)
@cfy.options.blueprint_id(required=True)
@cfy.options.inputs
@cfy.options.private_resource
@cfy.options.visibility(valid_values=VISIBILITY_EXCEPT_GLOBAL)
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.skip_plugins_validation
def manager_create(blueprint_id,
                   deployment_id,
                   inputs,
                   private_resource,
                   visibility,
                   logger,
                   client,
                   tenant_name,
                   skip_plugins_validation):
    """Create a deployment on the manager.

    `DEPLOYMENT_ID` is the id of the deployment you'd like to create.

    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Creating new deployment from blueprint {0}...'.format(
        blueprint_id))
    deployment_id = deployment_id or blueprint_id
    visibility = get_visibility(private_resource,
                                visibility,
                                logger,
                                valid_values=VISIBILITY_EXCEPT_GLOBAL)

    try:
        deployment = client.deployments.create(
            blueprint_id,
            deployment_id,
            inputs=inputs,
            visibility=visibility,
            skip_plugins_validation=skip_plugins_validation
        )
    except (MissingRequiredDeploymentInputError,
            UnknownDeploymentInputError) as e:
        logger.error('Unable to create deployment: {0}'.format(e.message))
        raise SuppressedCloudifyCliError(str(e))
    except DeploymentPluginNotFound as e:
        logger.info("Unable to create deployment. Not all "
                    "deployment plugins are installed on the Manager.{}"
                    "* Use 'cfy plugins upload' to upload the missing plugins"
                    " to the Manager, or use 'cfy deployments create' with "
                    "the '--skip-plugins-validation' flag "
                    " to skip this validation.".format(os.linesep))
        raise CloudifyCliError(str(e))
    except (UnknownDeploymentSecretError,
            UnsupportedDeploymentGetSecretError) as e:
        logger.info('Unable to create deployment due to invalid secret')
        raise CloudifyCliError(str(e))

    logger.info("Deployment created. The deployment's id is {0}".format(
        deployment.id))


@cfy.command(name='delete',
             short_help='Delete a deployment [manager only]')
@cfy.argument('deployment-id')
@cfy.options.force(help=helptexts.IGNORE_LIVE_NODES)
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_delete(deployment_id, force, logger, client, tenant_name):
    """Delete a deployment from the manager

    `DEPLOYMENT_ID` is the id of the deployment to delete.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Deleting deployment {0}...'.format(deployment_id))
    client.deployments.delete(deployment_id, force)
    logger.info("Deployment deleted")


@cfy.command(name='outputs',
             short_help='Show deployment outputs [manager only]')
@cfy.argument('deployment-id')
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_outputs(deployment_id, logger, client, tenant_name):
    """Retrieve outputs for a specific deployment

    `DEPLOYMENT_ID` is the id of the deployment to print outputs for.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Retrieving outputs for deployment {0}...'.format(
        deployment_id))
    dep = client.deployments.get(deployment_id, _include=['outputs'])
    outputs_def = dep.outputs
    response = client.deployments.outputs.get(deployment_id)
    outputs_ = StringIO()
    for output_name, output in response.outputs.iteritems():
        outputs_.write(' - "{0}":{1}'.format(output_name, os.linesep))
        description = outputs_def[output_name].get('description', '')
        outputs_.write('     Description: {0}{1}'.format(description,
                                                         os.linesep))
        outputs_.write('     Value: {0}{1}'.format(output, os.linesep))
    logger.info(outputs_.getvalue())


@cfy.command(name='inputs',
             short_help='Show deployment inputs [manager only]')
@cfy.argument('deployment-id')
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_inputs(deployment_id, logger, client, tenant_name):
    """Retrieve inputs for a specific deployment

    `DEPLOYMENT_ID` is the id of the deployment to print inputs for.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Retrieving inputs for deployment {0}...'.format(
        deployment_id))
    dep = client.deployments.get(deployment_id, _include=['inputs'])
    inputs_ = StringIO()
    for input_name, input in dep.inputs.iteritems():
        inputs_.write(' - "{0}":{1}'.format(input_name, os.linesep))
        inputs_.write('     Value: {0}{1}'.format(input, os.linesep))
    logger.info(inputs_.getvalue())


@cfy.command(name='set-visibility',
             short_help="Set the deployment's visibility [manager only]")
@cfy.argument('deployment-id')
@cfy.options.visibility(required=True, valid_values=[VisibilityState.TENANT])
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def manager_set_visibility(deployment_id, visibility, logger, client):
    """Set the deployment's visibility to tenant

    `DEPLOYMENT_ID` is the id of the deployment to update
    """
    validate_visibility(visibility, valid_values=[VisibilityState.TENANT])
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        client.deployments.set_visibility(deployment_id, visibility)
        logger.info('Deployment `{0}` was set to {1}'.format(deployment_id,
                                                             visibility))


@cfy.command(name='inputs', short_help='Show deployment inputs [locally]')
@cfy.options.verbose()
@cfy.options.blueprint_id(required=True, multiple_blueprints=True)
@cfy.pass_logger
def local_inputs(blueprint_id, logger):
    """Display inputs for the execution
    """
    env = load_env(blueprint_id)
    logger.info(json.dumps(env.plan['inputs'] or {}, sort_keys=True, indent=2))


@cfy.command(name='outputs', short_help='Show deployment outputs [locally]')
@cfy.options.verbose()
@cfy.options.blueprint_id(required=True, multiple_blueprints=True)
@cfy.pass_logger
def local_outputs(blueprint_id, logger):
    """Display outputs for the execution
    """
    env = load_env(blueprint_id)
    logger.info(json.dumps(env.outputs() or {}, sort_keys=True, indent=2))
