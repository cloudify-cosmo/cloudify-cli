########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import click

from .. import utils
from . import execute
from . import blueprints
from . import executions
from . import deployments
from ..config import options
from ..constants import DEFAULT_UNINSTALL_WORKFLOW


@click.command(name='uninstall', context_settings=utils.CLICK_CONTEXT_SETTINGS)
@click.argument('deployment-id')
@options.workflow_id('uninstall')
@options.parameters
@options.allow_custom_parameters
@options.timeout()
@options.include_logs
@options.json
@click.pass_context
def manager(ctx,
            deployment_id,
            workflow_id,
            parameters,
            allow_custom_parameters,
            timeout,
            include_logs,
            json):
    """Uninstall an application via the manager

    This will execute the `uninstall` workflow, delete the deployment and
    delete the blueprint (if there is only one deployment for that blueprint).
    """
    # Although the `uninstall` command does not use the `force` argument,
    # we are using the `executions start` handler as a part of it.
    # As a result, we need to provide it with a `force` argument, which is
    # defined below.
    force = False

    # if no workflow was supplied, execute the `uninstall` workflow
    workflow_id = workflow_id or DEFAULT_UNINSTALL_WORKFLOW

    ctx.invoke(
        executions.start,
        workflow_id=workflow_id,
        deployment_id=deployment_id,
        timeout=timeout,
        force=force,
        allow_custom_parameters=allow_custom_parameters,
        include_logs=include_logs,
        parameters=parameters,
        json=json)

    # before deleting the deployment, save its blueprint_id, so we will be able
    # to delete the blueprint after deleting the deployment
    client = utils.get_rest_client()
    deployment = client.deployments.get(
        deployment_id, _include=['blueprint_id'])
    blueprint_id = deployment.blueprint_id
    ctx.invoke(
        deployments.delete,
        deployment_id=deployment_id,
        ignore_live_nodes=False)
    ctx.invoke(
        blueprints.delete,
        blueprint_id=blueprint_id)


@click.command(name='uninstall', context_settings=utils.CLICK_CONTEXT_SETTINGS)
@options.workflow_id('uninstall')
@options.parameters
@options.allow_custom_parameters
@options.task_retries()
@options.task_retry_interval()
@options.task_thread_pool_size()
@click.pass_context
def local(ctx,
          workflow_id,
          parameters,
          allow_custom_parameters,
          task_retries,
          task_retry_interval,
          task_thread_pool_size):
    """Uninstall an application
    """
    # if no workflow was supplied, execute the `uninstall` workflow
    workflow_id = workflow_id or DEFAULT_UNINSTALL_WORKFLOW

    ctx.invoke(
        execute.execute,
        workflow_id=workflow_id,
        parameters=parameters,
        allow_custom_parameters=allow_custom_parameters,
        task_retries=task_retries,
        task_retry_interval=task_retry_interval,
        task_thread_pool_size=task_thread_pool_size)

    # Remove the local-storage dir
    utils.remove_if_exists(common.storage_dir())

    # Note that although `install` possibly creates a `.cloudify` dir in
    # addition to the creation of the local storage dir, `uninstall`
    # does not remove the .cloudify dir.
