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

import logger
from . import utils
from . import commands
from .config import cfy


@cfy.group(name='cfy')
@cfy.options.verbose
@cfy.options.version
def _cfy():
    """Cloudify's Command Line Interface

    Note that some commands are only available if you're using a manager.
    You can use a manager by running the `cfy use` command and providing
    it with the IP of your manager (and ssh credentials if applicable).
    """
    # TODO: When calling a command which only exists in the context
    # of a manager but no manager is currently `use`d, print out a message
    # stating that "Some commands only exist when using a manager. You can run
    # `cfy use MANAGER_IP` and try this command again."

    # TODO: Consider replacing `cfy init BLUEPRINT_PATH` with
    # `cfy blueprints init BLUEPRINT_PATH` for local.
    logger.configure_loggers()


def _register_commands():
    """Register the CLI's commands.

    Here is where we decide which commands register with the cli
    and which don't. We should decide that according to whether
    a manager is currently `use`d or not.
    """
    is_manager_active = utils.is_manager_active()

    _cfy.add_command(commands.use)
    _cfy.add_command(commands.init)
    _cfy.add_command(commands.recover)
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
        _cfy.add_command(commands.outputs)
        _cfy.add_command(commands.execute)


_register_commands()


if __name__ == '__main__':
    _cfy()
