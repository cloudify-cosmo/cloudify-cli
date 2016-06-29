########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import sys
import StringIO
import traceback

import click

from cloudify_rest_client.exceptions import NotModifiedError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.exceptions import MaintenanceModeActiveError
from cloudify_rest_client.exceptions import MaintenanceModeActivatingError

from . import utils
from . import logger
from . import commands
from .config import options
from .logger import get_logger
from .exceptions import CloudifyBootstrapError
from .exceptions import SuppressedCloudifyCliError


def _set_cli_except_hook(global_verbosity_level):

    def recommend(possible_solutions):
        logger = get_logger()

        logger.info('Possible solutions:')
        for solution in possible_solutions:
            logger.info('  - {0}'.format(solution))

    def new_excepthook(tpe, value, tb):
        logger = get_logger()

        prefix = None
        server_traceback = None
        output_message = True
        if issubclass(tpe, CloudifyClientError):
            server_traceback = value.server_traceback
            if not issubclass(
                    tpe,
                    (MaintenanceModeActiveError,
                     MaintenanceModeActivatingError,
                     NotModifiedError)):
                # this means we made a server call and it failed.
                # we should include this information in the error
                prefix = 'An error occurred on the server'
        if issubclass(tpe, SuppressedCloudifyCliError):
            output_message = False
        if issubclass(tpe, CloudifyBootstrapError):
            output_message = False
        if global_verbosity_level:
            # print traceback if verbose
            s_traceback = StringIO.StringIO()
            traceback.print_exception(
                etype=tpe,
                value=value,
                tb=tb,
                file=s_traceback)
            logger.error(s_traceback.getvalue())
            if server_traceback:
                logger.error('Server Traceback (most recent call last):')

                # No need for print_tb since this exception
                # is already formatted by the server
                logger.error(server_traceback)
        if output_message and not global_verbosity_level:

            # if we output the traceback
            # we output the message too.
            # print_exception does that.
            # here we just want the message (non verbose)
            if prefix:
                logger.error('{0}: {1}'.format(prefix, value))
            else:
                logger.error(value)
        if hasattr(value, 'possible_solutions'):
            recommend(getattr(value, 'possible_solutions'))

    sys.excepthook = new_excepthook


def register_commands():
    """Register the CLI's commands.

    Here is where we decide which commands register with the cli
    and which don't. We should decide that according to whether
    a manager is currently `use`d or not.
    """
    is_manager_active = utils.is_manager_active()

    cfy.add_command(commands.use)
    cfy.add_command(commands.init)
    cfy.add_command(commands.recover)
    cfy.add_command(commands.bootstrap)
    cfy.add_command(commands.validate_blueprint)
    cfy.add_command(commands.create_requirements)

    # TODO: Instead of manually stating each module,
    # we might want to try importing all modules in the `commands`
    # package recursively and check if they have a certain attribute
    # which indicates they belong to `manager`.
    if is_manager_active:
        cfy.add_command(commands.dev)
        cfy.add_command(commands.ssh)
        cfy.add_command(commands.logs)
        cfy.add_command(commands.nodes)
        cfy.add_command(commands.agents)
        cfy.add_command(commands.events)
        cfy.add_command(commands.groups)
        cfy.add_command(commands.status)
        cfy.add_command(commands.plugins)
        cfy.add_command(commands.upgrade)
        cfy.add_command(commands.teardown)
        cfy.add_command(commands.rollback)
        cfy.add_command(commands.workflows)
        cfy.add_command(commands.snapshots)
        cfy.add_command(commands.blueprints)
        cfy.add_command(commands.executions)
        cfy.add_command(commands.deployments)
        cfy.add_command(commands.install.manager)
        cfy.add_command(commands.maintenance_mode)
        cfy.add_command(commands.uninstall.manager)
        cfy.add_command(commands.node_instances.manager)
    else:
        cfy.add_command(commands.execute)
        cfy.add_command(commands.outputs)
        cfy.add_command(commands.install.local)
        cfy.add_command(commands.uninstall.local)
        cfy.add_command(commands.install_plugins)
        cfy.add_command(commands.node_instances.local)


@click.group(context_settings=utils.CLICK_CONTEXT_SETTINGS)
@options.verbose
@options.debug
@options.version
def cfy(verbose, debug):
    """Cloudify's Command Line Interface

    Note that some commands are only available if you're using a manager.
    You can use a manager by running the `cfy use` command and providing
    it with the IP of your manager.
    """
    # TODO: when calling a command which only exists in the context
    # of a manager but no manager is currently `use`d, print out a message
    # stating that "Some commands only exist when using a manager. You can run
    # `cfy use MANAGER_IP` and try this command again."
    # TODO: fix verbosity placement. Currently you can only declare the
    # verbosity level after `cfy` (i.e. `cfy -v`) and not after.
    logger.configure_loggers()
    logger.set_global_verbosity_level(verbose, debug)
    # _set_cli_except_hook(global_verbosity_level)


register_commands()


if __name__ == '__main__':
    cfy()
