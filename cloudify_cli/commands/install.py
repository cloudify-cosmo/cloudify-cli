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
import shutil

from cloudify_cli.cli import cfy, helptexts
from cloudify_cli.constants import DEFAULT_INSTALL_WORKFLOW
from cloudify_cli.blueprint import get_blueprint_path_and_id
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.commands import init, executions, blueprints, deployments


@cfy.command(name='install',
             short_help='Install an application blueprint [manager only]')
@cfy.argument('blueprint-path')
@cfy.options.blueprint_id(validate=True)
@cfy.options.blueprint_filename()
@cfy.options.validate
@cfy.options.deployment_id(validate=True)
@cfy.options.deployment_group_id
@cfy.options.group_count
@cfy.options.inputs
@cfy.options.workflow_id('install')
@cfy.options.force(help=helptexts.FORCE_CONCURRENT_EXECUTION)
@cfy.options.visibility()
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='blueprint and deployment')
@cfy.options.skip_plugins_validation
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.timeout()
@cfy.options.include_logs
@cfy.options.json_output
@cfy.options.blueprint_labels
@cfy.options.deployment_labels
@cfy.options.common_options
@cfy.pass_context
def manager(ctx,
            blueprint_path,
            blueprint_id,
            blueprint_filename,
            validate,
            deployment_id,
            deployment_group_id,
            count,
            inputs,
            workflow_id,
            force,
            visibility,
            tenant_name,
            skip_plugins_validation,
            parameters,
            allow_custom_parameters,
            timeout,
            include_logs,
            json_output,
            blueprint_labels,
            deployment_labels):
    """Install an application via the manager

    `BLUEPRINT_PATH` can be either a local blueprint yaml file or
    blueprint archive; a url to a blueprint archive or an
    `organization/blueprint_repo[:tag/branch]` (to be
    retrieved from GitHub).
    Supported archive types are: zip, tar, tar.gz and tar.bz2

    This will upload the blueprint, create a deployment and execute the
    `install` workflow.
    """
    processed_blueprint_path, blueprint_id = get_blueprint_path_and_id(
        blueprint_path,
        blueprint_filename,
        blueprint_id
    )
    if count is not None:
        if int(count) > 0:
            deployment_group_id = deployment_group_id or blueprint_id
        else:
            raise CloudifyCliError('Count must be a positive number.')
    else:
        deployment_id = deployment_id or blueprint_id

    if (deployment_group_id is None) != (count is None):
        raise CloudifyCliError('Both parameters must be provided: '
                               'deployment_group_id and count.')
    if (deployment_group_id is None) == (deployment_id is None):
        raise CloudifyCliError('One of the parameters must be provided: '
                               'deployment_group_id and deployment_id.')

    workflow_id = workflow_id or DEFAULT_INSTALL_WORKFLOW

    try:
        ctx.invoke(
            blueprints.upload,
            blueprint_path=processed_blueprint_path,
            blueprint_id=blueprint_id,
            blueprint_filename=blueprint_filename,
            validate=validate,
            visibility=visibility,
            tenant_name=tenant_name,
            labels=blueprint_labels
        )
    finally:
        # Every situation other than the user providing a path of a local
        # yaml means a temp folder will be created that should be later
        # removed.
        if processed_blueprint_path != blueprint_path:
            shutil.rmtree(os.path.dirname(os.path.dirname(
                processed_blueprint_path)))
    if deployment_id:
        ctx.invoke(
            deployments.manager_create,
            blueprint_id=blueprint_id,
            deployment_id=deployment_id,
            inputs=inputs,
            visibility=visibility,
            tenant_name=tenant_name,
            skip_plugins_validation=skip_plugins_validation,
            labels=deployment_labels
        )
        ctx.invoke(
            executions.manager_start,
            workflow_id=workflow_id,
            deployment_id=deployment_id,
            timeout=timeout,
            force=force,
            allow_custom_parameters=allow_custom_parameters,
            include_logs=include_logs,
            parameters=parameters,
            json_output=json_output,
            tenant_name=tenant_name
        )
    else:
        ctx.invoke(
            deployments.groups_create,
            deployment_group_name=deployment_group_id,
            inputs=inputs,
            default_blueprint=blueprint_id,
        )
        ctx.invoke(
            deployments.groups_extend,
            deployment_group_name=deployment_group_id,
            count=count,
        )
        ctx.invoke(
            executions.execution_groups_start,
            deployment_group=deployment_group_id,
            workflow_id=workflow_id,
            parameters=parameters,
            json_output=json_output,
            force=force,
            timeout=timeout
        )


@cfy.command(name='install',
             short_help='Install an application blueprint [locally]')
@cfy.argument('blueprint-path')
@cfy.options.blueprint_filename()
@cfy.options.blueprint_id(required=False, validate=True)
@cfy.options.inputs
@cfy.options.validate
@cfy.options.install_plugins
@cfy.options.workflow_id('install')
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.task_retries(5)
@cfy.options.task_retry_interval(3)
@cfy.options.task_thread_pool_size()
@cfy.options.common_options
@cfy.pass_context
def local(ctx,
          blueprint_path,
          blueprint_filename,
          blueprint_id,
          inputs,
          validate,
          install_plugins,
          workflow_id,
          parameters,
          allow_custom_parameters,
          task_retries,
          task_retry_interval,
          task_thread_pool_size):
    """Install an application

    `BLUEPRINT_PATH` can be a:
        - local blueprint yaml file
        - blueprint archive
        - url to a blueprint archive
        - github repo (`organization/blueprint_repo[:tag/branch]`)

    Supported archive types are: zip, tar, tar.gz and tar.bz2

    """
    processed_blueprint_path, blueprint_id = get_blueprint_path_and_id(
        blueprint_path,
        blueprint_filename,
        blueprint_id
    )

    workflow_id = workflow_id or DEFAULT_INSTALL_WORKFLOW

    try:
        if validate:
            ctx.invoke(
                blueprints.validate_blueprint,
                blueprint_path=processed_blueprint_path)
        ctx.invoke(
            init.init,
            blueprint_id=blueprint_id,
            blueprint_path=processed_blueprint_path,
            inputs=inputs,
            install_plugins=install_plugins)
    finally:
        # Every situation other than the user providing a path of a local
        # yaml means a temp folder will be created that should be later
        # removed.
        if processed_blueprint_path != blueprint_path:
            shutil.rmtree(os.path.dirname(os.path.dirname(
                processed_blueprint_path)))
    ctx.invoke(
        executions.local_start,
        workflow_id=workflow_id,
        blueprint_id=blueprint_id,
        parameters=parameters,
        allow_custom_parameters=allow_custom_parameters,
        task_retries=task_retries,
        task_retry_interval=task_retry_interval,
        task_thread_pool_size=task_thread_pool_size)
