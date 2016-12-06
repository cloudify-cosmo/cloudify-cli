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

from . import init
from ..cli import cfy
from . import executions
from . import blueprints
from .. import blueprint
from . import deployments
from ..constants import DEFAULT_INSTALL_WORKFLOW


@cfy.command(name='install',
             short_help='Install an application blueprint [manager only]')
@cfy.argument('blueprint-path')
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
@cfy.options.json_output
@cfy.options.verbose()
@cfy.pass_context
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
            json_output):
    """Install an application via the manager

    `BLUEPRINT_PATH` can be either a local blueprint yaml file or
    blueprint archive; a url to a blueprint archive or an
    `organization/blueprint_repo[:tag/branch]` (to be
    retrieved from GitHub).
    Supported archive types are: zip, tar, tar.gz and tar.bz2

    This will upload the blueprint, create a deployment and execute the
    `install` workflow.
    """
    processed_blueprint_path, blueprint_id = _get_blueprint_path_and_id(
        blueprint_path,
        blueprint_filename,
        blueprint_id
    )
    deployment_id = deployment_id or blueprint_id
    workflow_id = workflow_id or DEFAULT_INSTALL_WORKFLOW

    # Although the `install` command does not need the `force` argument,
    # we *are* using the `executions start` handler as a part of it.
    # as a result, we need to provide it with a `force` argument, which is
    # defined below.
    force = False

    try:
        ctx.invoke(
            blueprints.upload,
            blueprint_path=processed_blueprint_path,
            blueprint_id=blueprint_id,
            blueprint_filename=blueprint_filename,
            validate=validate)
    finally:
        # Every situation other than the user providing a path of a local
        # yaml means a temp folder will be created that should be later
        # removed.
        if processed_blueprint_path != blueprint_path:
            shutil.rmtree(os.path.dirname(os.path.dirname(
                processed_blueprint_path)))
    ctx.invoke(
        deployments.manager_create,
        blueprint_id=blueprint_id,
        deployment_id=deployment_id,
        inputs=inputs)
    ctx.invoke(
        executions.manager_start,
        workflow_id=workflow_id,
        deployment_id=deployment_id,
        timeout=timeout,
        force=force,
        allow_custom_parameters=allow_custom_parameters,
        include_logs=include_logs,
        parameters=parameters,
        json_output=json_output)


@cfy.command(name='install',
             short_help='Install an application blueprint [locally]')
@cfy.argument('blueprint-path')
@cfy.options.blueprint_filename()
@cfy.options.blueprint_id(required=False, multiple_blueprints=True)
@cfy.options.inputs
@cfy.options.validate
@cfy.options.install_plugins
@cfy.options.workflow_id('install')
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.task_retries(5)
@cfy.options.task_retry_interval(3)
@cfy.options.task_thread_pool_size()
@cfy.options.verbose()
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
    processed_blueprint_path, blueprint_id = _get_blueprint_path_and_id(
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


def _get_blueprint_path_and_id(blueprint_path,
                               blueprint_filename,
                               blueprint_id):
    processed_blueprint_path = blueprint.get(
        blueprint_path,
        blueprint_filename,
        download=True,
    )

    blueprint_id = blueprint_id or blueprint.generate_id(
        processed_blueprint_path,
        blueprint_filename
    )

    return processed_blueprint_path, blueprint_id
