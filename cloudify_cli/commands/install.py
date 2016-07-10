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
@click.argument('blueprint-path')
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
    # # The presence of the `archive_location` argument is used to distinguish
    # # between `install` in 'blueprints upload' mode,
    # # and `install` in 'blueprints publish archive' mode.
    # if archive_location:
    #     blueprints.check_if_archive_type_is_supported(archive_location)

    #     if not blueprint_filename:
    #         blueprint_filename = DEFAULT_BLUEPRINT_FILE_NAME

    # If blueprint_id wasn't supplied, assign it to the name of the archive
    #     if not blueprint_id:
    #         blueprint_id = blueprints.get_blueprint_id(archive_location)

    #     # auto-generate blueprint id if necessary
    #     if _auto_generate_ids(auto_generate_ids):
    #         blueprint_id = utils._generate_suffixed_id(blueprint_id)

    #     blueprints.publish_archive(archive_location,
    #                                blueprint_filename,
    #                                blueprint_id)
    # else:
    #     blueprint_path_supplied = bool(blueprint_path)
    #     if not blueprint_path:
    #         blueprint_path = os.path.join(utils.get_cwd(),
    #                                       DEFAULT_BLUEPRINT_PATH)

    #     # If blueprint_id wasn't supplied, assign it to the name of
    #     # folder containing the application's blueprint file.
    #     if not blueprint_id:
    #         blueprint_id = os.path.basename(
    #             os.path.dirname(
    #                 os.path.abspath(blueprint_path)))

    #     # Try opening `blueprint_path`, since `blueprints.upload` expects the
    #     # `blueprint_path` argument to be a file.
    #     # (The reason for this is beyond me. That's just the way it is)

    #     if _auto_generate_ids(auto_generate_ids):
    #         blueprint_id = utils._generate_suffixed_id(blueprint_id)

    #     try:
    #         with open(blueprint_path) as blueprint_file:
    #             blueprints.upload(blueprint_file,
    #                               blueprint_id,
    #                               validate)
    #     except IOError as e:

    #         # No such file or directory
    #         if not blueprint_path_supplied and e.errno == errno.ENOENT:
    #             raise CloudifyCliError(
    #                 'Your blueprint was not found in the path: {0}.\n\n'
    #                 'Consider providing an explicit path to your blueprint '
    #                 'using the `-p`/`--blueprint-path` flag, like so:\n'
    #                 '`cfy install -p /path/to/blueprint_file.yaml`\n'
    #                 .format(blueprint_path)
    #             )
    #         else:
    #             raise CloudifyCliError(
    #                 'A problem was encountered while trying to open '
    #                 '{0}.\n({1})'.format(blueprint_path, e))

    blueprint_id = blueprint_id or utils._generate_suffixed_id(
        blueprints.get_archive_id(blueprint_path))
    deployment_id = deployment_id or utils._generate_suffixed_id(blueprint_id)
    workflow_id = workflow_id or DEFAULT_INSTALL_WORKFLOW
    if not inputs and os.path.isfile(os.path.join(
            utils.get_cwd(), DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND)):
        inputs = DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND
    # although the `install` command does not need the `force` argument,
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
@click.argument('blueprint-path')
@cfy.options.inputs
@cfy.options.install_plugins
@cfy.options.workflow_id('install')
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.task_retries(5)
@cfy.options.task_retry_interval(3)
@cfy.options.task_thread_pool_size()
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
