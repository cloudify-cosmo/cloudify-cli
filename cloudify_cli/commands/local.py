########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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
# * See the License for the specific language governing permissions and
#    * limitations under the License.

"""
Handles all commands that start with 'cfy local'
"""

import os
import json
import shutil

import click

from cloudify.workflows import local

from cloudify_cli import utils
from cloudify_cli import common
from cloudify_cli import exceptions
from cloudify_cli.logger import get_logger
from cloudify_cli.commands import init as cfy_init
from cloudify_cli.commands import (helptexts, envvars)
from cloudify_cli.constants import DEFAULT_BLUEPRINT_PATH
from cloudify_cli.constants import DEFAULT_INSTALL_WORKFLOW
from cloudify_cli.constants import DEFAULT_UNINSTALL_WORKFLOW
from cloudify_cli.constants import DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND


_NAME = 'local'
_STORAGE_DIR_NAME = 'local-storage'


@click.group(name='local', context_settings=utils.CLICK_CONTEXT_SETTINGS)
def local_group():
    """Handle local environments
    """
    pass


@local_group.command(name='install')
@click.argument('blueprint-path',
                required=True,
                envvar=envvars.BLUEPRINT_PATH,
                type=click.Path(exists=True))
@click.option('-i',
              '--inputs',
              multiple=True,
              help=helptexts.INPUTS)
@click.option('--install-plugins',
              is_flag=True,
              help=helptexts.INSTALL_PLUGINS)
@click.option('-w',
              '--workflow-id',
              help=helptexts.EXECUTE_DEFAULT_INSTALL_WORKFLOW)
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
def install(blueprint_path,
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
    # if no blueprint path was supplied, set it to a default value
    if not blueprint_path:
        blueprint_path = DEFAULT_BLUEPRINT_PATH

    # If no inputs were supplied, and there is a file named inputs.yaml in
    # the cwd, use it as the inputs file
    if not inputs:
        if os.path.isfile(
                os.path.join(utils.get_cwd(),
                             DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND)):

            inputs = DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND

    init(blueprint_path=blueprint_path,
         inputs=inputs,
         install_plugins=install_plugins)

    # if no workflow was supplied, execute the `install` workflow
    if not workflow_id:
        workflow_id = DEFAULT_INSTALL_WORKFLOW

    execute(workflow_id=workflow_id,
            parameters=parameters,
            allow_custom_parameters=allow_custom_parameters,
            task_retries=task_retries,
            task_retry_interval=task_retry_interval,
            task_thread_pool_size=task_thread_pool_size)


@local_group.command(name='uninstall')
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
def uninstall(workflow_id,
              parameters,
              allow_custom_parameters,
              task_retries,
              task_retry_interval,
              task_thread_pool_size):
    """Uninstall an application
    """
    # if no workflow was supplied, execute the `uninstall` workflow
    if not workflow_id:
        workflow_id = DEFAULT_UNINSTALL_WORKFLOW

    execute(workflow_id=workflow_id,
            parameters=parameters,
            allow_custom_parameters=allow_custom_parameters,
            task_retries=task_retries,
            task_retry_interval=task_retry_interval,
            task_thread_pool_size=task_thread_pool_size)

    # Remove the local-storage dir
    utils.remove_if_exists(_storage_dir())

    # Note that although `local install` possibly creates a `.cloudify` dir in
    # addition to the creation of the local storage dir, `local uninstall`
    # does not remove the .cloudify dir.


@local_group.command(name='init')
@click.argument('blueprint-path',
                required=True,
                envvar=envvars.BLUEPRINT_PATH,
                type=click.Path(exists=True))
@click.option('-i',
              '--inputs',
              multiple=True,
              help=helptexts.INPUTS)
@click.option('--install-plugins',
              is_flag=True,
              help=helptexts.INSTALL_PLUGINS)
# The 'overshadowing' of the `install_plugins` parameter is totally fine
def init(blueprint_path,
         inputs,
         install_plugins):
    """Initialize a local environment in the current working directory
    """
    if os.path.isdir(_storage_dir()):
        shutil.rmtree(_storage_dir())

    if not utils.is_initialized():
        cfy_init(reset_config=False, skip_logging=True)
    try:
        common.initialize_blueprint(
            blueprint_path=blueprint_path,
            name=_NAME,
            inputs=inputs,
            storage=_storage(),
            install_plugins=install_plugins,
            resolver=utils.get_import_resolver()
        )
    except ImportError as e:

        # import error indicates
        # some plugin modules are missing
        # TODO - consider adding an error code to
        # TODO - all of our exceptions. so that we
        # TODO - easily identify them here
        e.possible_solutions = [
            "Run `cfy local init --install-plugins -p {0}`"
            .format(blueprint_path),
            "Run `cfy local install-plugins -p {0}`"
            .format(blueprint_path)
        ]
        raise

    get_logger().info("Initiated {0}\nIf you make changes to the "
                      "blueprint, run `cfy local init -p {0}` "
                      "again to apply them".format(blueprint_path))


@local_group.command(name='execute')
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
def execute(workflow_id,
            parameters,
            allow_custom_parameters,
            task_retries,
            task_retry_interval,
            task_thread_pool_size):
    """Execute a workflow
    """
    logger = get_logger()
    parameters = utils.inputs_to_dict(parameters, 'parameters')
    env = _load_env()
    result = env.execute(workflow=workflow_id,
                         parameters=parameters,
                         allow_custom_parameters=allow_custom_parameters,
                         task_retries=task_retries,
                         task_retry_interval=task_retry_interval,
                         task_thread_pool_size=task_thread_pool_size)
    if result is not None:
        logger.info(json.dumps(result,
                               sort_keys=True,
                               indent=2))


@local_group.command(name='outputs')
def outputs():
    """Display outputs for the execution
    """
    logger = get_logger()
    env = _load_env()
    logger.info(json.dumps(env.outputs() or {},
                           sort_keys=True,
                           indent=2))


@local_group.command(name='instances')
@click.argument('node-id', required=True)
def instances(node_id):
    """Display node-instances for the execution
    """
    logger = get_logger()
    env = _load_env()
    node_instances = env.storage.get_node_instances()
    if node_id:
        node_instances = [instance for instance in node_instances
                          if instance.node_id == node_id]
        if not node_instances:
            raise exceptions.CloudifyCliError(
                'Could not find node {0}'.format(node_id))
    logger.info(json.dumps(node_instances,
                           sort_keys=True,
                           indent=2))


@local_group.command(name='install-plugins')
@click.argument('blueprint-path',
                required=True,
                envvar=envvars.BLUEPRINT_PATH,
                type=click.Path(exists=True))
def install_plugins(blueprint_path):
    """Install the necessary plugins for a given blueprint
    """
    common.install_blueprint_plugins(blueprint_path=blueprint_path)


@local_group.command(name='create-requirements')
@click.argument('blueprint-path',
                required=True,
                envvar=envvars.BLUEPRINT_PATH,
                type=click.Path(exists=True))
@click.option('-o',
              '--output-path',
              help=helptexts.OUTPUT_PATH)
def create_requirements(blueprint_path, output_path):
    """Create a pip-compliant requirements file for a given blueprint
    """
    logger = get_logger()
    if output_path and os.path.exists(output_path):
        raise exceptions.CloudifyCliError(
            'Output path {0} already exists'.format(output_path))

    requirements = common.create_requirements(blueprint_path=blueprint_path)

    if output:
        utils.dump_to_file(requirements, output_path)
        logger.info('Requirements file created successfully --> {0}'
                    .format(output_path))
    else:
        # we don't want to use just lgr
        # since we want this output to be prefix free.
        # this will make it possible to pipe the
        # output directly to pip
        for requirement in requirements:
            print(requirement)
            logger.info(requirement)


def _storage_dir():
    return os.path.join(utils.get_cwd(), _STORAGE_DIR_NAME)


def _storage():
    return local.FileStorage(storage_dir=_storage_dir())


def _load_env():
    if not os.path.isdir(_storage_dir()):
        error = exceptions.CloudifyCliError(
            '{0} has not been initialized with a blueprint.'.format(
                utils.get_cwd()))

        # init was probably not executed.
        # suggest solution.

        error.possible_solutions = [
            "Run `cfy local init` in this directory"
        ]
        raise error
    return local.load_env(name=_NAME,
                          storage=_storage())
