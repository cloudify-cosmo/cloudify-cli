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

"""
Handles 'cfy uninstall'
"""
import click

from cloudify_cli import utils
from cloudify_cli.commands import local
from cloudify_cli.config import helptexts
from cloudify_cli.commands import blueprints
from cloudify_cli.commands import executions
from cloudify_cli.commands import deployments
from cloudify_cli.constants import DEFAULT_UNINSTALL_WORKFLOW


@click.command(name='uninstall', context_settings=utils.CLICK_CONTEXT_SETTINGS)
@click.argument('deployment-id')
@click.option('-w',
              '--workflow-id',
              help=helptexts.EXECUTE_DEFAULT_UNINSTALL_WORKFLOW)
@click.option('-p',
              '--parameters',
              help=helptexts.PARAMETERS)
@click.option('--allow-custom-parameters',
              is_flag=True,
              help=helptexts.ALLOW_CUSTOM_PARAMETERS)
@click.option('--timeout',
              type=int,
              default=900,
              help=helptexts.OPERATION_TIMEOUT)
@click.option('-l',
              '--include-logs',
              is_flag=True,
              help=helptexts.INCLUDE_LOGS)
@click.option('--json',
              is_flag=True,
              help=helptexts.JSON_OUTPUT)
def remote_uninstall(deployment_id,
                     workflow_id,
                     parameters,
                     allow_custom_parameters,
                     timeout,
                     include_logs,
                     json):

    # Although the `uninstall` command does not use the `force` argument,
    # we are using the `executions start` handler as a part of it.
    # As a result, we need to provide it with a `force` argument, which is
    # defined below.
    force = False

    # if no workflow was supplied, execute the `uninstall` workflow
    workflow_id = workflow_id or DEFAULT_UNINSTALL_WORKFLOW

    executions.start(workflow_id=workflow_id,
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

    deployments.delete(deployment_id, ignore_live_nodes=False)

    blueprints.delete(blueprint_id)


@click.command(name='uninstall', context_settings=utils.CLICK_CONTEXT_SETTINGS)
@click.option('-w',
              '--workflow-id',
              help=helptexts.EXECUTE_DEFAULT_UNINSTALL_WORKFLOW)
@click.option('-p',
              '--parameters',
              help=helptexts.PARAMETERS)
@click.option('--allow-custom-parameters',
              is_flag=True,
              help=helptexts.ALLOW_CUSTOM_PARAMETERS)
@click.option('--task-retries',
              type=int,
              default=0,
              help=helptexts.TASK_RETRIES)
@click.option('--task-retry-interval',
              type=int,
              default=1,
              help=helptexts.TASK_RETRIES)
@click.option('--task-thread-pool-size',
              type=int,
              default=1,
              help=helptexts.TASK_THREAD_POOL_SIZE)
def local_uninstall(workflow_id,
                    parameters,
                    allow_custom_parameters,
                    task_retries,
                    task_retry_interval,
                    task_thread_pool_size):
    """Uninstall an application
    """
    # if no workflow was supplied, execute the `uninstall` workflow
    workflow_id = workflow_id or DEFAULT_UNINSTALL_WORKFLOW

    local.execute(workflow_id=workflow_id,
                  parameters=parameters,
                  allow_custom_parameters=allow_custom_parameters,
                  task_retries=task_retries,
                  task_retry_interval=task_retry_interval,
                  task_thread_pool_size=task_thread_pool_size)

    # Remove the local-storage dir
    utils.remove_if_exists(local._storage_dir())

    # Note that although `local install` possibly creates a `.cloudify` dir in
    # addition to the creation of the local storage dir, `local uninstall`
    # does not remove the .cloudify dir.
