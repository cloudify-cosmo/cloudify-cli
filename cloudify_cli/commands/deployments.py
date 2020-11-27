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

import click

from cloudify._compat import StringIO
from cloudify_rest_client.constants import VISIBILITY_EXCEPT_PRIVATE
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
from ..table import (
    print_data,
    print_single,
    print_details,
    print_list
)
from ..cli import cfy, helptexts
from ..logger import (CloudifyJSONEncoder,
                      get_events_logger,
                      get_global_json_output,
                      output)
from .. import env, execution_events_fetcher, utils
from ..constants import DEFAULT_BLUEPRINT_PATH, DELETE_DEP
from ..blueprint import get_blueprint_path_and_id
from ..exceptions import (CloudifyCliError,
                          SuppressedCloudifyCliError,
                          ExecutionTimeoutError)
from ..utils import (prettify_client_error,
                     get_visibility,
                     validate_visibility,
                     get_deployment_environment_execution)
from .summary import BASE_SUMMARY_FIELDS, structure_summary_results


DEPLOYMENT_COLUMNS = [
    'id', 'blueprint_id', 'created_at', 'updated_at', 'visibility',
    'tenant_name', 'created_by', 'site_name'
]
DEPLOYMENT_UPDATE_COLUMNS = [
    'id', 'deployment_id', 'tenant_name', 'state', 'execution_id',
    'created_at', 'visibility', 'old_blueprint_id', 'new_blueprint_id'
]
DEPLOYMENT_UPDATE_PREVIEW_COLUMNS = [
    'deployment_id', 'tenant_name', 'state', 'created_at', 'visibility',
    'old_blueprint_id', 'new_blueprint_id'
]
NON_PREVIEW_COLUMNS = ['id', 'execution_id']
STEPS_COLUMNS = ['entity_type', 'entity_id', 'action']
DEPENDENCIES_COLUMNS = ['deployment', 'dependency_type', 'dependent_node',
                        'tenant']
TENANT_HELP_MESSAGE = 'The name of the tenant of the deployment'
DEPLOYMENTS_SUMMARY_FIELDS = (['blueprint_id', 'site_name'] +
                              BASE_SUMMARY_FIELDS)
# for human-redable outputs, those fields are formatted separately. In
# machine-readable (json) output, they are just part of the output
MACHINE_READABLE_UPDATE_PREVIEW_COLUMNS = [
    'old_inputs', 'new_inputs', 'steps', 'modified_entity_ids',
    'installed_nodes', 'uninstalled_nodes', 'reinstalled_nodes',
    'explicit_reinstall', 'recursive_dependencies'
]


@cfy.group(name='deployments')
@cfy.options.common_options
def deployments():
    """Handle deployments on the Manager
    """
    pass


def _print_single_update(deployment_update_dict,
                         explicit_reinstall=None,
                         preview=False,
                         skip_install=False,
                         skip_uninstall=False,
                         skip_reinstall=False):
    if explicit_reinstall is None:
        explicit_reinstall = []
    if preview:
        columns = DEPLOYMENT_UPDATE_PREVIEW_COLUMNS
    else:
        columns = DEPLOYMENT_UPDATE_COLUMNS

    deployment_update_dict['explicit_reinstall'] = explicit_reinstall
    deployment_update_dict['installed_nodes'] = []
    deployment_update_dict['uninstalled_nodes'] = []
    deployment_update_dict['reinstalled_nodes'] = []
    for step in deployment_update_dict['steps']:
        entity = step['entity_id'].split(':')
        if entity[0] != 'nodes':
            continue
        if step['action'] == 'add':
            deployment_update_dict['installed_nodes'].append(entity[1])
        elif step['action'] == 'remove':
            deployment_update_dict['uninstalled_nodes'].append(entity[1])
        elif step['action'] == 'modify':
            deployment_update_dict['reinstalled_nodes'].append(entity[1])

    if get_global_json_output():
        columns += MACHINE_READABLE_UPDATE_PREVIEW_COLUMNS

    print_single(columns,
                 deployment_update_dict,
                 'Deployment Update:',
                 max_width=50)

    if not get_global_json_output():
        skip_msg = ' (will be skipped)'
        print_details(deployment_update_dict['old_inputs'] or {},
                      'Old inputs:')
        print_details(deployment_update_dict['new_inputs'] or {},
                      'New inputs:')
        print_data(STEPS_COLUMNS,
                   deployment_update_dict['steps'] or {},
                   'Steps:')
        print_list(
            deployment_update_dict['installed_nodes'] or [],
            'Installed nodes{0}:'.format(skip_msg if skip_install else '')
        )
        print_list(
            deployment_update_dict['uninstalled_nodes'] or [],
            'Uninstalled nodes{0}:'.format(skip_msg if skip_uninstall else '')
        )
        print_list(deployment_update_dict['reinstalled_nodes'] or [],
                   'Automatically detected nodes to reinstall{0}:'
                   .format(skip_msg if skip_reinstall else ''))
        print_list(explicit_reinstall, 'Expicitly given nodes to reinstall:')
        print_data(DEPENDENCIES_COLUMNS,
                   deployment_update_dict['recursive_dependencies'] or {},
                   'Affected (recursively) dependent deployments:')


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
    _print_single_update(deployment_update_dict)


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
@cfy.options.preview
@cfy.options.dont_update_plugins
@cfy.options.force(help=helptexts.FORCE_UPDATE)
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.visibility(mutually_exclusive_required=False)
@cfy.options.validate
@cfy.options.include_logs
@cfy.options.json_output
@cfy.options.common_options
@cfy.options.runtime_only_evaluation
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
                   preview,
                   dont_update_plugins,
                   workflow_id,
                   force,
                   include_logs,
                   json_output,
                   logger,
                   client,
                   tenant_name,
                   blueprint_id,
                   visibility,
                   validate,
                   runtime_only_evaluation):
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
        logger.warning(
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
    reinstall_list = reinstall_list or []
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
            reinstall_list,
            preview,
            not dont_update_plugins,
            runtime_only_evaluation=runtime_only_evaluation
        )

    if preview:
        _print_single_update(deployment_update,
                             explicit_reinstall=reinstall_list,
                             preview=True,
                             skip_install=skip_install,
                             skip_uninstall=skip_uninstall,
                             skip_reinstall=skip_reinstall)
        return

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
@cfy.options.visibility()
@cfy.options.site_name
@cfy.options.labels
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.runtime_only_evaluation
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.skip_plugins_validation
def manager_create(blueprint_id,
                   deployment_id,
                   inputs,
                   private_resource,
                   visibility,
                   site_name,
                   labels,
                   logger,
                   client,
                   tenant_name,
                   skip_plugins_validation,
                   runtime_only_evaluation):
    """Create a deployment on the manager.

    `DEPLOYMENT_ID` is the id of the deployment you'd like to create.

    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Creating new deployment from blueprint {0}...'.format(
        blueprint_id))
    deployment_id = deployment_id or blueprint_id
    visibility = get_visibility(private_resource, visibility, logger)

    try:
        deployment = client.deployments.create(
            blueprint_id,
            deployment_id,
            inputs=inputs,
            visibility=visibility,
            skip_plugins_validation=skip_plugins_validation,
            site_name=site_name,
            runtime_only_evaluation=runtime_only_evaluation,
            labels=labels
        )
    except (MissingRequiredDeploymentInputError,
            UnknownDeploymentInputError) as e:
        logger.error('Unable to create deployment: {0}'.format(e))
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
@cfy.options.force(help=helptexts.FORCE_DELETE_DEPLOYMENT)
@cfy.options.common_options
@cfy.options.with_logs
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_delete(deployment_id, force, with_logs, logger, client,
                   tenant_name):
    """Delete a deployment from the manager

    `DEPLOYMENT_ID` is the id of the deployment to delete.
    """

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Trying to delete deployment {0}...'.format(deployment_id))
    client.deployments.delete(deployment_id, force,
                              with_logs=with_logs)
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

    except CloudifyClientError as e:
        # ignore 404 errors for the execution or deployment - it was already
        # deleted before we were able to follow it
        if 'not found' not in str(e):
            raise

    except RuntimeError as e:
        # ignore the failure to get the execution - it was already deleted
        # before we were able to follow it
        if 'Failed to get' not in str(e):
            raise

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
    _present_outputs_or_capabilities(
        'outputs',
        deployment_id,
        tenant_name,
        logger,
        client
    )


@cfy.command(name='capabilities',
             short_help='Show deployment capabilities [manager only]')
@cfy.argument('deployment-id')
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def manager_capabilities(deployment_id, logger, client, tenant_name):
    """Retrieve capabilities for a specific deployment

    `DEPLOYMENT_ID` is the id of the deployment to print capabilities for.
    """
    _present_outputs_or_capabilities(
        'capabilities',
        deployment_id,
        tenant_name,
        logger,
        client
    )


def _present_outputs_or_capabilities(
        resource, deployment_id, tenant_name, logger, client
):
    # resource is either "outputs" or "capabilities"

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info(
        'Retrieving {0} for deployment {1}...'.format(resource, deployment_id)
    )
    dep = client.deployments.get(deployment_id, _include=[resource])
    definitions = getattr(dep, resource)
    client_api = getattr(client.deployments, resource)
    response = client_api.get(deployment_id)
    values_dict = getattr(response, resource)
    if get_global_json_output():
        values = {out: {
            'value': val,
            'description': definitions[out].get('description')
        } for out, val in values_dict.items()}
        print_details(values, 'Deployment {0}:'.format(resource))
    else:
        values = StringIO()
        for elem_name, elem in values_dict.items():
            values.write(' - "{0}":{1}'.format(elem_name, os.linesep))
            description = definitions[elem_name].get('description', '')
            values.write('     Description: {0}{1}'.format(description,
                                                           os.linesep))
            values.write(
                '     Value: {0}{1}'.format(elem, os.linesep))
        logger.info(values.getvalue())


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
@cfy.options.visibility(required=True, valid_values=VISIBILITY_EXCEPT_PRIVATE)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def manager_set_visibility(deployment_id, visibility, logger, client):
    """Set the deployment's visibility to tenant

    `DEPLOYMENT_ID` is the id of the deployment to update
    """
    validate_visibility(visibility, valid_values=VISIBILITY_EXCEPT_PRIVATE)
    status_codes = [400, 403, 404]
    with prettify_client_error(status_codes, logger):
        client.deployments.set_visibility(deployment_id, visibility)
        logger.info('Deployment `{0}` was set to {1}'.format(deployment_id,
                                                             visibility))


@cfy.command(name='inputs', short_help='Show deployment inputs [locally]')
@cfy.options.common_options
@cfy.options.blueprint_id(required=True)
@cfy.pass_logger
def local_inputs(blueprint_id, logger):
    """Display inputs for the execution
    """
    env = load_env(blueprint_id)
    logger.info(json.dumps(env.plan['inputs'] or {}, sort_keys=True, indent=2))


@cfy.command(name='outputs', short_help='Show deployment outputs [locally]')
@cfy.options.common_options
@cfy.options.blueprint_id(required=True)
@cfy.pass_logger
def local_outputs(blueprint_id, logger):
    """Display outputs for the execution
    """
    env = load_env(blueprint_id)
    logger.info(json.dumps(env.outputs() or {}, sort_keys=True, indent=2))


@deployments.command(name='summary',
                     short_help='Retrieve summary of deployment details '
                                '[manager only]')
@cfy.argument('target_field', type=click.Choice(DEPLOYMENTS_SUMMARY_FIELDS))
@cfy.argument('sub_field', type=click.Choice(DEPLOYMENTS_SUMMARY_FIELDS),
              default=None, required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def summary(target_field, sub_field, logger, client, tenant_name,
            all_tenants):
    """Retrieve summary of deployments, e.g. a count of each deployment with
    the same blueprint ID.

    `TARGET_FIELD` is the field to summarise deployments on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of deployments on field {field}'.format(
        field=target_field))

    summary = client.summary.deployments.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
    )

    columns, items = structure_summary_results(
        summary.items,
        target_field,
        sub_field,
        'deployments',
    )

    print_data(
        columns,
        items,
        'Deployment summary by {field}'.format(field=target_field),
    )


@cfy.command(name='set-site',
             short_help="Set the deployment's site [manager only]")
@cfy.argument('deployment-id')
@cfy.options.site_name
@cfy.options.detach_site
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def manager_set_site(deployment_id, site_name, detach_site, client, logger):
    """Set the deployment's site

    `DEPLOYMENT_ID` is the id of the deployment to update
    """
    if not (site_name or detach_site):
        raise CloudifyCliError(
            'Must provide either a `--site-name` of a valid site or '
            '`--detach-site` (for detaching the current site of '
            'the given deployment)'
        )

    client.deployments.set_site(deployment_id,
                                site_name=site_name,
                                detach_site=detach_site)
    if detach_site:
        logger.info('The site of `{0}` was detached'.format(deployment_id))
    else:
        logger.info('The site of `{0}` was set to {1}'.format(deployment_id,
                                                              site_name))


@deployments.group(name='labels',
                   short_help="Handle the deployments' labels")
@cfy.options.common_options
def labels():
    if not env.is_initialized():
        env.raise_uninitialized()


@labels.command(name='list',
                short_help="List the deployments' labels")
@cfy.argument('deployment-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def list_labels(deployment_id,
                logger,
                client,
                tenant_name):
    deployment_labels = {}
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing labels of deployment {0}...'.format(deployment_id))

    raw_deployment_labels = client.deployments.get(deployment_id)['labels']
    for label in raw_deployment_labels:
        label_key, label_value = label['key'], label['value']
        deployment_labels.setdefault(label_key, [])
        deployment_labels[label_key].append(label_value)

    printable_deployments_labels = [
        {'key': dep_label_key, 'values': dep_label_values}
        for dep_label_key, dep_label_values in deployment_labels.items()
    ]

    if get_global_json_output():
        output(json.dumps(deployment_labels, cls=CloudifyJSONEncoder))
    else:
        print_data(['key', 'values'],
                   printable_deployments_labels,
                   'Deployment labels',
                   max_width=50)


@labels.command(name='add',
                short_help="Add labels to a specific deployment")
@cfy.argument('labels-list',
              callback=cfy.parse_and_validate_labels)
@cfy.argument('deployment-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def add_labels(labels_list,
               deployment_id,
               logger,
               client,
               tenant_name):
    """LABELS_LIST: <key>:<value>,<key>:<value>"""

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Adding labels to deployment {0}...'.format(deployment_id))

    deployment_labels = _get_deployment_labels(client, deployment_id)
    curr_labels_set = labels_list_to_set(deployment_labels)
    provided_labels_set = labels_list_to_set(labels_list)

    new_labels = provided_labels_set.difference(curr_labels_set)
    if new_labels:
        updated_labels = _labels_set_to_list(
            curr_labels_set.union(provided_labels_set))
        client.deployments.update_labels(deployment_id, updated_labels)
        logger.info(
            'The following label(s) were added successfully to deployment '
            '{0}: {1}'.format(deployment_id, _labels_set_to_list(new_labels)))
    else:
        logger.info('The provided labels are already assigned to deployment '
                    '{0}. No labels were added.'.format(deployment_id))


@labels.command(name='delete',
                short_help="Delete labels from a specific deployment")
@cfy.argument('label', callback=cfy.parse_and_validate_label_to_delete)
@cfy.argument('deployment-id')
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete_labels(label,
                  deployment_id,
                  logger,
                  client,
                  tenant_name):
    """
    LABEL: Can be either <key>:<value> or <key>. If <key> is provided,
    all labels associated with this key will be deleted from the deployment.
    """

    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Deleting labels from deployment {0}...'.format(deployment_id))
    deployment_labels = _get_deployment_labels(client, deployment_id)

    updated_labels = []
    labels_to_delete = []
    if isinstance(label, dict):
        if label in deployment_labels:
            labels_to_delete = [label]
            deployment_labels.remove(label)
            updated_labels = deployment_labels
    else:  # A label key was provided
        for dep_label in deployment_labels:
            if label in dep_label:
                labels_to_delete.append(dep_label)
            else:
                updated_labels.append(dep_label)

    if labels_to_delete:
        client.deployments.update_labels(deployment_id, updated_labels)
        logger.info(
            'The following label(s) were deleted successfully from deployment '
            '{0}: {1}'.format(deployment_id, labels_to_delete))
    else:
        logger.info('The provided labels are not assigned to deployment '
                    '{0}. No labels were deleted.'.format(deployment_id))


def _get_deployment_labels(client, deployment_id):
    raw_deployment_labels = client.deployments.get(deployment_id)['labels']
    return [{dep_label['key']: dep_label['value']}
            for dep_label in raw_deployment_labels]


def _labels_set_to_list(labels_set):
    return [{key: value} for key, value in labels_set]


def labels_list_to_set(labels_list):
    labels_set = set()
    for label in labels_list:
        [(key, value)] = label.items()
        labels_set.add((key, value))

    return labels_set
