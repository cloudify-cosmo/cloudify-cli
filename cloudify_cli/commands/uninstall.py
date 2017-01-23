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

from .. import env
from .. import utils
from ..cli import cfy
from . import blueprints
from . import executions
from . import deployments
from ..local import storage_dir
from ..constants import DEFAULT_UNINSTALL_WORKFLOW


@cfy.command(name='uninstall',
             short_help='Uninstall an application blueprint [manager only]')
@cfy.argument('deployment-id')
@cfy.options.workflow_id('uninstall')
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.timeout()
@cfy.options.include_logs
@cfy.options.json_output
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.pass_context
def manager(ctx,
            deployment_id,
            workflow_id,
            parameters,
            allow_custom_parameters,
            timeout,
            include_logs,
            json_output,
            tenant_name):
    """Uninstall an application via the manager

    This will execute the `uninstall` workflow, delete the deployment and
    delete the blueprint (if there is only one deployment for that blueprint).

    `DEPLOYMENT_ID` is the id of the deployment to uninstall.
    """
    env.assert_manager_active()

    # Although the `uninstall` command does not use the `force` argument,
    # we are using the `executions start` handler as a part of it.
    # As a result, we need to provide it with a `force` argument, which is
    # defined below.
    force = False

    # if no workflow was supplied, execute the `uninstall` workflow
    workflow_id = workflow_id or DEFAULT_UNINSTALL_WORKFLOW

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
        tenant_name=tenant_name)

    # before deleting the deployment, save its blueprint_id, so we will be able
    # to delete the blueprint after deleting the deployment
    client = env.get_rest_client(tenant_name=tenant_name)
    deployment = client.deployments.get(
        deployment_id, _include=['blueprint_id'])
    blueprint_id = deployment.blueprint_id
    ctx.invoke(
        deployments.manager_delete,
        deployment_id=deployment_id,
        force=False,
        tenant_name=tenant_name)
    ctx.invoke(
        blueprints.delete,
        blueprint_id=blueprint_id,
        tenant_name=tenant_name)


@cfy.command(name='uninstall',
             short_help='Uninstall an application blueprint')
@cfy.options.workflow_id('uninstall')
@cfy.options.blueprint_id(required=True, multiple_blueprints=True)
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.task_retries()
@cfy.options.task_retry_interval()
@cfy.options.task_thread_pool_size()
@cfy.options.verbose()
@cfy.pass_context
def local(ctx,
          workflow_id,
          blueprint_id,
          parameters,
          allow_custom_parameters,
          task_retries,
          task_retry_interval,
          task_thread_pool_size):
    """Uninstall an application
    """
    workflow_id = workflow_id or DEFAULT_UNINSTALL_WORKFLOW

    ctx.invoke(
        executions.local_start,
        blueprint_id=blueprint_id,
        workflow_id=workflow_id,
        parameters=parameters,
        allow_custom_parameters=allow_custom_parameters,
        task_retries=task_retries,
        task_retry_interval=task_retry_interval,
        task_thread_pool_size=task_thread_pool_size)

    # Remove the local-storage dir
    utils.remove_if_exists(storage_dir(blueprint_id))
