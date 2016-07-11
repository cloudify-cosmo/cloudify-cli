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

from cloudify_rest_client.exceptions import NotModifiedError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.exceptions import MaintenanceModeActiveError
from cloudify_rest_client.exceptions import MaintenanceModeActivatingError

from . import utils
from . import logger
from . import commands
from .config import cfy
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

    _cfy.add_command(commands.use)
    _cfy.add_command(commands.init)
    _cfy.add_command(commands.recover)
    _cfy.add_command(commands.validate)
    _cfy.add_command(commands.bootstrap)
    _cfy.add_command(commands.profiles)
    _cfy.add_command(commands.create_requirements)

    # TODO: Instead of manually stating each module,
    # we might want to try importing all modules in the `commands`
    # package recursively and check if they have a certain attribute
    # which indicates they belong to `manager`.
    if is_manager_active:
        _cfy.add_command(commands.dev)
        _cfy.add_command(commands.ssh)
        _cfy.add_command(commands.logs)
        _cfy.add_command(commands.agents)
        _cfy.add_command(commands.events)
        _cfy.add_command(commands.status)
        _cfy.add_command(commands.upgrade)
        _cfy.add_command(commands.teardown)
        _cfy.add_command(commands.rollback)
        _cfy.add_command(commands.snapshots)
        _cfy.add_command(commands.install.manager)
        _cfy.add_command(commands.maintenance_mode)
        _cfy.add_command(commands.uninstall.manager)
        _cfy.add_command(commands.node_instances.manager)

        # TODO: consolidate with `local` of the same type
        _cfy.add_command(commands.nodes)
        _cfy.add_command(commands.groups)
        _cfy.add_command(commands.plugins)
        _cfy.add_command(commands.workflows)
        _cfy.add_command(commands.blueprints)
        _cfy.add_command(commands.executions)
        _cfy.add_command(commands.deployments)

    else:
        _cfy.add_command(commands.install.local)
        _cfy.add_command(commands.uninstall.local)
        _cfy.add_command(commands.install_plugins)
        _cfy.add_command(commands.node_instances.local)

        # TODO: consolidate with `manager` of the same type
        _cfy.add_command(commands.inputs)
        _cfy.add_command(commands.execute)
        _cfy.add_command(commands.outputs)


@cfy.group(name='cfy')
@cfy.options.verbose
@cfy.options.debug
@cfy.options.version
def _cfy(verbose, debug):
    """Cloudify's Command Line Interface

    Note that some commands are only available if you're using a manager.
    You can use a manager by running the `cfy use` command and providing
    it with the IP of your manager (and ssh credentials if applicable).
    """
    # TODO: When calling a command which only exists in the context
    # of a manager but no manager is currently `use`d, print out a message
    # stating that "Some commands only exist when using a manager. You can run
    # `cfy use MANAGER_IP` and try this command again."
    # TODO: Fix verbosity placement. Currently you can only declare the
    # verbosity level after `cfy` (i.e. `cfy -v`) and not after.
    logger.configure_loggers()
    logger.set_global_verbosity_level(verbose, debug)
    # _set_cli_except_hook(verbose)

    # TODO: Consider replacing `cfy init BLUEPRINT_PATH` with
    # `cfy blueprints init BLUEPRINT_PATH` for local.

register_commands()


if __name__ == '__main__':
    _cfy()
