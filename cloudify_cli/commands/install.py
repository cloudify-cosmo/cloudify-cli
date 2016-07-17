########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import os

import click

from . import init
from .. import utils
from . import execute
from ..config import cfy
from . import blueprints
from . import executions
from . import deployments
from ..constants import DEFAULT_BLUEPRINT_PATH
from ..constants import DEFAULT_INSTALL_WORKFLOW
from ..constants import DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND


@cfy.command(name='install')
@cfy.options.blueprint_id()
@cfy.options.blueprint_filename()
@cfy.options.validate
@cfy.options.deployment_id()
@cfy.options.inputs
@cfy.options.workflow_id('install')
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.timeout()
@cfy.options.include_logs
@cfy.options.json
@cfy.options.verbose
@click.argument('blueprint-path')
@click.pass_context
def manager(ctx,
            blueprint_path,
            blueprint_id,
            blueprint_filename,
            validate,
            deployment_id,
            inputs,
            workflow_id,
            parameters,
            allow_custom_parameters,
            timeout,
            include_logs,
            json):
    """Install an application via the manager

    This will upload the blueprint, create a deployment and execute the
    `install` workflow.
    """
    blueprint_id = blueprint_id or utils._generate_suffixed_id(
        blueprints.get_archive_id(blueprint_path))
    deployment_id = deployment_id or utils._generate_suffixed_id(blueprint_id)
    workflow_id = workflow_id or DEFAULT_INSTALL_WORKFLOW
    if not inputs and os.path.isfile(os.path.join(
            utils.get_cwd(), DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND)):
        inputs = DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND
    # Although the `install` command does not need the `force` argument,
    # we *are* using the `executions start` handler as a part of it.
    # as a result, we need to provide it with a `force` argument, which is
    # defined below.
    force = False

    ctx.invoke(
        blueprints.upload,
        blueprint_path=blueprint_path,
        blueprint_id=blueprint_id,
        blueprint_filename=blueprint_filename,
        validate=validate)
    ctx.invoke(
        deployments.create,
        blueprint_id=blueprint_id,
        deployment_id=deployment_id,
        inputs=inputs)
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


@cfy.command(name='install')
@cfy.options.inputs
@cfy.options.install_plugins
@cfy.options.workflow_id('install')
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.task_retries(5)
@cfy.options.task_retry_interval(3)
@cfy.options.task_thread_pool_size()
@cfy.options.verbose
@click.argument('blueprint-path')
@click.pass_context
def local(ctx,
          blueprint_path,
          inputs,
          install_plugins,
          workflow_id,
          parameters,
          allow_custom_parameters,
          task_retries,
          task_retry_interval,
          task_thread_pool_size):
    """Install an application
    """
    blueprint_path = blueprint_path or DEFAULT_BLUEPRINT_PATH
    workflow_id = workflow_id or DEFAULT_INSTALL_WORKFLOW
    if not inputs and os.path.isfile(os.path.join(
            utils.get_cwd(), DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND)):
        inputs = DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND

    ctx.invoke(
        init.init,
        blueprint_path=blueprint_path,
        inputs=inputs,
        install_plugins=install_plugins)
    ctx.invoke(
        execute.execute,
        workflow_id=workflow_id,
        parameters=parameters,
        allow_custom_parameters=allow_custom_parameters,
        task_retries=task_retries,
        task_retry_interval=task_retry_interval,
        task_thread_pool_size=task_thread_pool_size)
