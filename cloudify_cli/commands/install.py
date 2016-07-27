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
import shutil

import click

from .. import utils
from .. import common
from ..config import cfy
from ..logger import get_logger
from ..exceptions import CloudifyCliError
from ..constants import DEFAULT_INSTALL_WORKFLOW
from ..constants import DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND

from . import init
from . import blueprints
from . import executions
from . import deployments


@cfy.command(name='install',
             short_help='Install an application blueprint [manager only]')
@cfy.argument('blueprint-path', required=False)
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

    `BLUEPRINT_PATH` can be either a local blueprint yaml file or
    blueprint archive; a url to a blueprint archive or an
    `organization/blueprint_repo[:tag/branch]` (to be
    retrieved from GitHub)

    This will upload the blueprint, create a deployment and execute the
    `install` workflow.
    """
    if not blueprint_path:
        processed_blueprint_path = _get_default_blueprint_path(
            blueprint_path, blueprint_filename)
    else:
        processed_blueprint_path = common.get_blueprint(
            blueprint_path, blueprint_filename)

    blueprint_id = blueprint_id or common.get_blueprint_id(
        processed_blueprint_path, blueprint_filename)
    deployment_id = deployment_id or blueprint_id
    workflow_id = workflow_id or DEFAULT_INSTALL_WORKFLOW
    if not inputs and os.path.isfile(os.path.join(
            utils.get_cwd(), DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND)):
        inputs = DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND

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
        json=json)


@cfy.command(name='install',
             short_help='Install an application blueprint [locally]')
@cfy.argument('blueprint-path', required=False)
@cfy.options.blueprint_filename()
@cfy.options.inputs
@cfy.options.validate
@cfy.options.install_plugins
@cfy.options.workflow_id('install')
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.task_retries(5)
@cfy.options.task_retry_interval(3)
@cfy.options.task_thread_pool_size()
@cfy.options.verbose
@click.pass_context
def local(ctx,
          blueprint_path,
          blueprint_filename,
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

    `BLUEPRINT_PATH` can be either a local blueprint yaml file or
    blueprint archive; a url to a blueprint archive or an
    `organization/blueprint_repo[:tag/branch]` (to be
    retrieved from GitHub)
    """
    if not blueprint_path:
        processed_blueprint_path = _get_default_blueprint_path(
            blueprint_path, blueprint_filename)
    else:
        processed_blueprint_path = common.get_blueprint(
            blueprint_path, blueprint_filename)

    workflow_id = workflow_id or DEFAULT_INSTALL_WORKFLOW
    if not inputs and os.path.isfile(os.path.join(
            utils.get_cwd(), DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND)):
        inputs = DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND

    try:
        if validate:
            ctx.invoke(
                blueprints.validate_blueprint,
                blueprint_path=processed_blueprint_path)
        ctx.invoke(
            init.init,
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
        parameters=parameters,
        allow_custom_parameters=allow_custom_parameters,
        task_retries=task_retries,
        task_retry_interval=task_retry_interval,
        task_thread_pool_size=task_thread_pool_size)


def _get_default_blueprint_path(blueprint_path, blueprint_filename):
    logger = get_logger()
    logger.info('No blueprint path provided. Looking for {0} in the '
                'cwd.'.format(blueprint_filename))
    blueprint_path = os.path.abspath(blueprint_filename)
    if not os.path.isfile(blueprint_path):
        raise CloudifyCliError(
            'Could not find `{0}` in the cwd. Please provide a path to a '
            'blueprint yaml file using the `-n/--blueprint-filename` flag '
            'or a path to a blueprint file.'.format(blueprint_filename))
