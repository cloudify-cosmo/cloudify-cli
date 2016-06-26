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

# TODO: just import the commands package
from . import utils
from . import logger
from .logger import configure_loggers
from .exceptions import CloudifyBootstrapError
from .exceptions import SuppressedCloudifyCliError

from .commands import use
from .commands import dev
from .commands import ssh
from .commands import init
from .commands import logs
from .commands import nodes
from .commands import agents
from .commands import events
from .commands import groups
from .commands import status
from .commands import install
from .commands import recover
from .commands import version
from .commands import plugins
from .commands import upgrade
from .commands import validate
from .commands import teardown
from .commands import rollback
from .commands import uninstall
from .commands import workflows
from .commands import snapshots
from .commands import bootstrap
from .commands import blueprints
from .commands import executions
from .commands import deployments
from .commands import maintenance
from .commands import node_instances


def _set_cli_except_hook():

    def recommend(possible_solutions):

        from cloudify_cli.logger import get_logger
        logger = get_logger()

        logger.info('Possible solutions:')
        for solution in possible_solutions:
            logger.info('  - {0}'.format(solution))

    def new_excepthook(tpe, value, tb):

        from cloudify_cli.logger import get_logger
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
        if verbosity_level:
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
        if output_message and not verbosity_level:

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

    main.add_command(use.use)
    main.add_command(recover.recover)
    main.add_command(init.init_command)
    main.add_command(validate.validate)
    main.add_command(bootstrap.bootstrap)

    # TODO: Instead of manually stating each module,
    # we should try to import all modules in the `commands`
    # package recursively and check if they have a certain attribute
    # which indicates they belong to `manager`.
    if is_manager_active:
        main.add_command(dev.dev)
        main.add_command(ssh.ssh)
        main.add_command(logs.logs)
        main.add_command(nodes.nodes)
        main.add_command(agents.agents)
        main.add_command(events.events)
        main.add_command(groups.groups)
        main.add_command(status.status)
        main.add_command(plugins.plugins)
        main.add_command(upgrade.upgrade)
        main.add_command(teardown.teardown)
        main.add_command(rollback.rollback)
        main.add_command(workflows.workflows)
        main.add_command(snapshots.snapshots)
        main.add_command(blueprints.blueprints)
        main.add_command(executions.executions)
        main.add_command(install.remote_install)
        main.add_command(deployments.deployments)
        main.add_command(uninstall.remote_uninstall)
        main.add_command(maintenance.maintenance_mode)
        main.add_command(node_instances.node_instances)
    else:
        main.add_command(install.local_install)
        main.add_command(uninstall.local_uninstall)
        main.add_command(node_instances.node_instances_command)


@click.group(context_settings=utils.CLICK_CONTEXT_SETTINGS)
@click.option('-v',
              '--verbose',
              count=True,
              is_eager=True)
@click.option('--debug',
              default=False,
              is_flag=True)
@click.option('--version',
              is_flag=True,
              callback=version.version,
              expose_value=False,
              is_eager=True)
def main(verbose, debug):
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
    configure_loggers()

    if debug:
        global_verbosity_level = logger.HIGH_VERBOSE
    else:
        global_verbosity_level = verbose
    logger.set_global_verbosity_level(global_verbosity_level)
    if global_verbosity_level >= logger.HIGH_VERBOSE:
        logger.set_debug()
    # _set_cli_except_hook()


register_commands()


if __name__ == '__main__':
    main()
