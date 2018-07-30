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

from StringIO import StringIO

from cloudify_rest_client.constants import (VisibilityState,
                                            VISIBILITY_EXCEPT_GLOBAL)
from cloudify_rest_client.exceptions import (
    DeploymentPluginNotFound,
    UnknownDeploymentInputError,
    UnknownDeploymentSecretError,
    MissingRequiredDeploymentInputError,
    UnsupportedDeploymentGetSecretError,
    CloudifyClientError
)
from . import blueprints
from ..local import load_env
from ..table import print_data, print_single, print_details
from ..cli import cfy, helptexts
from ..logger import get_events_logger, get_global_json_output
from .. import execution_events_fetcher, utils
from ..constants import DEFAULT_BLUEPRINT_PATH, DELETE_DEP
from ..blueprint import get_blueprint_path_and_id
from ..exceptions import (CloudifyCliError,
                          SuppressedCloudifyCliError,
                          ExecutionTimeoutError)
from ..utils import (prettify_client_error,
                     get_visibility,
                     validate_visibility,
                     get_deployment_environment_execution)


DEPLOYMENT_COLUMNS = ['id', 'blueprint_id', 'created_at', 'updated_at',
                      'visibility', 'tenant_name', 'created_by']
DEPLOYMENT_UPDATE_COLUMNS = ['id', 'deployment_id', 'tenant_name', 'state',
                             'execution_id', 'created_at', 'visibility',
                             'old_blueprint_id', 'new_blueprint_id']
TENANT_HELP_MESSAGE = 'The name of the tenant of the deployment'


@cfy.group(name='deployments')
@cfy.options.common_options
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
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_list(blueprint_id,
                 sort_by,
                 descending,
                 all_tenants,
                 search,
                 pagination_offset,
                 pagination_size,
                 logger,
                 client,
                 tenant_name):
    """List deployments

    If `--blueprint-id` is provided, list deployments for that blueprint.
    Otherwise, list deployments for all blueprints.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    if blueprint_id:
        logger.info('Listing deployments for blueprint {0}...'.format(
            blueprint_id))
    else:
        logger.info('Listing all deployments...')

    deployments = client.deployments.list(sort=sort_by,
                                          is_descending=descending,
                                          _all_tenants=all_tenants,
                                          _search=search,
                                          _offset=pagination_offset,
                                          _size=pagination_size,
                                          blueprint_id=blueprint_id)
    total = deployments.metadata.pagination.total
    print_data(DEPLOYMENT_COLUMNS, deployments, 'Deployments:')
    logger.info('Showing {0} of {1} deployments'.format(len(deployments),
                                                        total))


@cfy.command(name='history', short_help='List deployment updates '
                                        '[manager only]')
@cfy.options.deployment_id()
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='deployment update')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_history(deployment_id,
                    sort_by,
                    descending,
                    all_tenants,
                    search,
                    pagination_offset,
                    pagination_size,
                    logger,
                    client,
                    tenant_name):
    """Show deployment history by listing deployment updates

    If `--deployment-id` is provided, list deployment updates for that
    deployment. Otherwise, list deployment updates for all deployments.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    if deployment_id:
        logger.info('Listing deployment updates for deployment {0}...'.format(
            deployment_id))
    else:
        logger.info('Listing all deployment updates...')

    deployment_updates = client.deployment_updates.list(
        sort=sort_by,
        is_descending=descending,
        _all_tenants=all_tenants,
        _search=search,
        _offset=pagination_offset,
        _size=pagination_size,
        deployment_id=deployment_id
    )
    total = deployment_updates.metadata.pagination.total
    print_data(
        DEPLOYMENT_UPDATE_COLUMNS, deployment_updates, 'Deployment updates:')
    logger.info('Showing {0} of {1} deployment updates'.format(
        len(deployment_updates), total))


@cfy.command(
    name='get-update',
    short_help='Retrieve deployment update information [manager only]'
)
@cfy.argument('deployment-update-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='deployment update')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_get_update(deployment_update_id, logger, client, tenant_name):
    """Retrieve information for a specific deployment update

    `DEPLOYMENT_UPDATE_ID` is the id of the deployment update to get
    information on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info(
        'Retrieving deployment update {0}...'.format(deployment_update_id))
    deployment_update_dict = client.deployment_updates.get(
        deployment_update_id)
    columns = DEPLOYMENT_UPDATE_COLUMNS
    if get_global_json_output():
        columns += ['old_inputs', 'new_inputs']
    print_single(columns,
                 deployment_update_dict,
                 'Deployment Update:',
                 max_width=50)

    if not get_global_json_output():
        print_details(deployment_update_dict['old_inputs'] or {},
                      'Old inputs:')
        print_details(deployment_update_dict['new_inputs'] or {},
                      'New inputs:')


@cfy.command(name='update', short_help='Update a deployment [manager only]')
@cfy.argument('deployment-id')
@cfy.options.blueprint_path()
@cfy.options.blueprint_filename(' [DEPRECATED]')
@cfy.options.blueprint_id()
@cfy.options.inputs
@cfy.options.reinstall_list
@cfy.options.workflow_id()
@cfy.options.skip_install
@cfy.options.skip_uninstall
@cfy.options.skip_reinstall
@cfy.options.ignore_failure
@cfy.options.install_first
@cfy.options.force(help=helptexts.FORCE_UPDATE)
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.visibility(mutually_exclusive_required=False)
@cfy.options.validate
@cfy.options.include_logs
@cfy.options.json_output
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.pass_context
def manager_update(ctx,
                   deployment_id,
                   blueprint_path,
                   inputs,
                   reinstall_list,
                   blueprint_filename,
                   skip_install,
                   skip_uninstall,
                   skip_reinstall,
                   ignore_failure,
                   install_first,
                   workflow_id,
                   force,
                   include_logs,
                   json_output,
                   logger,
                   client,
                   tenant_name,
                   blueprint_id,
                   visibility,
                   validate):
    """Update a specified deployment according to the specified blueprint.
    The blueprint can be supplied as an id of a blueprint that already exists
    in the system (recommended).
    The other way (not recommended) is to supply a blueprint to upload and
    use it to update the deployment [DEPRECATED]
    Note: using the deprecated way will upload the blueprint and then use it
    to update the deployment. So doing it twice with the same blueprint may
    fail because the blueprint id in the system will already exist. In this
    case it is better to use the first and recommended way, and simply pass
    the blueprint id.

    `DEPLOYMENT_ID` is the deployment's id to update.
    """
    if not any([blueprint_id, blueprint_path, inputs]):
        raise CloudifyCliError(
            'Must supply either a blueprint (by id of an existing blueprint, '
            'or a path to a new blueprint), or new inputs')
    if (not blueprint_path or not utils.is_archive(blueprint_path)) \
            and blueprint_filename not in (DEFAULT_BLUEPRINT_PATH,
                                           blueprint_path):
        raise CloudifyCliError(
            '--blueprint-filename param should be passed only when updating '
            'from an archive, so --blueprint-path must be passed as a path to '
            'a blueprint archive'
        )

    if blueprint_path:
        logger.warn(
            'DEPRECATED: passing a path to blueprint for deployment update '
            'is deprecated, and it is recommended instead to pass an id of '
            'a blueprint that is already in the system. Note that '
            'the blueprint passed will be added to the system and '
            'then deployment update will start.'
        )
        processed_blueprint_path, blueprint_id = get_blueprint_path_and_id(
            blueprint_path, blueprint_filename, blueprint_id)
        try:
            ctx.invoke(blueprints.upload,
                       blueprint_path=processed_blueprint_path,
                       blueprint_id=blueprint_id,
                       blueprint_filename=blueprint_filename,
                       validate=validate,
                       visibility=visibility,
                       tenant_name=tenant_name)
        finally:
            # Every situation other than the user providing a path of a local
            # yaml means a temp folder will be created that should be later
            # removed.
            if processed_blueprint_path != blueprint_path:
                shutil.rmtree(os.path.dirname(os.path.dirname(
                    processed_blueprint_path)))
    elif tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))

    msg = 'Updating deployment {0}'.format(deployment_id)
    if inputs:
        msg += ' with new inputs'
    if blueprint_id:
        msg += ', using blueprint {0}'.format(blueprint_id)
    logger.info(msg)
    deployment_update = \
        client.deployment_updates.update_with_existing_blueprint(
            deployment_id,
            blueprint_id,
            inputs,
            skip_install,
            skip_uninstall,
            skip_reinstall,
            workflow_id,
            force,
            ignore_failure,
            install_first,
            list(reinstall_list)
        )
    events_logger = get_events_logger(json_output)
    execution = execution_events_fetcher.wait_for_execution(
        client,
        client.executions.get(deployment_update.execution_id),
        events_handler=events_logger,
        include_logs=include_logs,
        timeout=None  # don't timeout ever
    )

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
@cfy.argument('deployment-id', required=False, callback=cfy.validate_name)
@cfy.options.blueprint_id(required=True)
@cfy.options.inputs
@cfy.options.private_resource
@cfy.options.visibility(valid_values=VISIBILITY_EXCEPT_GLOBAL)
@cfy.options.common_options
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
    utils.explicit_tenant_name_message(tenant_name, logger)
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
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_delete(deployment_id, force, logger, client, tenant_name):
    """Delete a deployment from the manager

    `DEPLOYMENT_ID` is the id of the deployment to delete.
    """

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Trying to delete deployment {0}...'.format(deployment_id))
    client.deployments.delete(deployment_id, force)
    try:
        execution = get_deployment_environment_execution(
            client, deployment_id, DELETE_DEP)
        if execution:
            execution_events_fetcher.wait_for_execution(
                client, execution, timeout=18, logger=logger)

    except ExecutionTimeoutError:
        raise CloudifyCliError(
            'Timed out waiting for deployment `{0}` to be deleted. Please '
            'execute `cfy deployments list` to check whether the '
            'deployment has been deleted.'.format(deployment_id))

    # The deployemnt might be deleted from the DB before we are able to
    # retrieve it, and that's fine
    except CloudifyClientError as e:
        if ('`Deployment` with ID `{0}` was not found'.format(deployment_id)
                in e.message):
            pass

    logger.info("Deployment deleted")


@cfy.command(name='outputs',
             short_help='Show deployment outputs [manager only]')
@cfy.argument('deployment-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_outputs(deployment_id, logger, client, tenant_name):
    """Retrieve outputs for a specific deployment

    `DEPLOYMENT_ID` is the id of the deployment to print outputs for.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving outputs for deployment {0}...'.format(
        deployment_id))
    dep = client.deployments.get(deployment_id, _include=['outputs'])
    outputs_def = dep.outputs
    response = client.deployments.outputs.get(deployment_id)
    if get_global_json_output():
        outputs = {out: {
            'value': val,
            'description': outputs_def[out].get('description')
        } for out, val in response.outputs.items()}
        print_details(outputs, 'Deployment outputs:')
    else:
        outputs_ = StringIO()
        for output_name, output in response.outputs.items():
            outputs_.write(' - "{0}":{1}'.format(output_name, os.linesep))
            description = outputs_def[output_name].get('description', '')
            outputs_.write('     Description: {0}{1}'.format(description,
                                                             os.linesep))
            outputs_.write('     Value: {0}{1}'.format(output, os.linesep))
        logger.info(outputs_.getvalue())


@cfy.command(name='inputs',
             short_help='Show deployment inputs [manager only]')
@cfy.argument('deployment-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_inputs(deployment_id, logger, client, tenant_name):
    """Retrieve inputs for a specific deployment

    `DEPLOYMENT_ID` is the id of the deployment to print inputs for.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving inputs for deployment {0}...'.format(
        deployment_id))
    dep = client.deployments.get(deployment_id, _include=['inputs'])
    if get_global_json_output():
        print_details(dep.inputs, 'Deployment inputs:')
    else:
        inputs_ = StringIO()
        for input_name, input in dep.inputs.items():
            inputs_.write(' - "{0}":{1}'.format(input_name, os.linesep))
            inputs_.write('     Value: {0}{1}'.format(input, os.linesep))
        logger.info(inputs_.getvalue())


@cfy.command(name='set-visibility',
             short_help="Set the deployment's visibility [manager only]")
@cfy.argument('deployment-id')
@cfy.options.visibility(required=True, valid_values=[VisibilityState.TENANT])
@cfy.options.common_options
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
@cfy.options.common_options
@cfy.options.blueprint_id(required=True, multiple_blueprints=True)
@cfy.pass_logger
def local_inputs(blueprint_id, logger):
    """Display inputs for the execution
    """
    env = load_env(blueprint_id)
    logger.info(json.dumps(env.plan['inputs'] or {}, sort_keys=True, indent=2))


@cfy.command(name='outputs', short_help='Show deployment outputs [locally]')
@cfy.options.common_options
@cfy.options.blueprint_id(required=True, multiple_blueprints=True)
@cfy.pass_logger
def local_outputs(blueprint_id, logger):
    """Display outputs for the execution
    """
    env = load_env(blueprint_id)
    logger.info(json.dumps(env.outputs() or {}, sort_keys=True, indent=2))
