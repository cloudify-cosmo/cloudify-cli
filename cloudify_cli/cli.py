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
from .config import cfy


from commands import install
from commands import uninstall
from commands import node_instances

from commands.use import use
from commands.dev import dev
from commands.ssh import ssh
from commands.init import init
from commands.logs import logs
from commands.nodes import nodes
from commands.agents import agents
from commands.events import events
from commands.groups import groups
from commands.status import status
from commands.inputs import inputs
from commands.outputs import outputs
from commands.execute import execute
from commands.recover import recover
from commands.plugins import plugins
from commands.upgrade import upgrade
from commands.teardown import teardown
from commands.rollback import rollback
from commands.profiles import profiles
from commands.workflows import workflows
from commands.snapshots import snapshots
from commands.bootstrap import bootstrap
from commands.blueprints import blueprints
from commands.executions import executions
from commands.deployments import deployments
from commands.install_plugins import install_plugins
from commands.maintenance_mode import maintenance_mode
from commands.create_requirements import create_requirements


@cfy.group(name='cfy')
@cfy.options.verbose
@cfy.options.version
def _cfy():
    """Cloudify's Command Line Interface

    Note that some commands are only available if you're using a manager.
    You can use a manager by running the `cfy use` command and providing
    it with the IP of your manager (and ssh credentials if applicable).

    To activate bash-completion. Run: `eval "$(_CFY_COMPLETE=source cfy)"`

    Cloudify's working directory resides in ~/.cloudify. To change it, set
    the variable `CFY_WORKDIR` to something else (e.g. /tmp/).
    """
    # TODO: When calling a command which only exists in the context
    # of a manager but no manager is currently `use`d, print out a message
    # stating that "Some commands only exist when using a manager. You can run
    # `cfy use MANAGER_IP` and try this command again."
    logger.configure_loggers()


def _register_commands():
    """Register the CLI's commands.

    Here is where we decide which commands register with the cli
    and which don't. We should decide that according to whether
    a manager is currently `use`d or not.
    """
    is_manager_active = utils.is_manager_active()

    _cfy.add_command(use)
    _cfy.add_command(init)
    _cfy.add_command(recover)
    _cfy.add_command(bootstrap)
    _cfy.add_command(profiles)
    _cfy.add_command(create_requirements)

    # TODO: Instead of manually stating each module,
    # we might want to try importing all modules in the `commands`
    # package recursively and check if they have a certain attribute
    # which indicates they belong to `manager`.
    if is_manager_active:
        _cfy.add_command(dev)
        _cfy.add_command(ssh)
        _cfy.add_command(logs)
        _cfy.add_command(agents)
        _cfy.add_command(events)
        _cfy.add_command(status)
        _cfy.add_command(upgrade)
        _cfy.add_command(teardown)
        _cfy.add_command(rollback)
        _cfy.add_command(snapshots)
        _cfy.add_command(install.manager)
        _cfy.add_command(maintenance_mode)
        _cfy.add_command(uninstall.manager)
        _cfy.add_command(node_instances.manager)

        # TODO: consolidate with `local` of the same type
        _cfy.add_command(nodes)
        _cfy.add_command(groups)
        _cfy.add_command(plugins)
        _cfy.add_command(workflows)
        _cfy.add_command(blueprints)
        _cfy.add_command(executions)
        _cfy.add_command(deployments)

    else:
        _cfy.add_command(install.local)
        _cfy.add_command(uninstall.local)
        _cfy.add_command(install_plugins)
        _cfy.add_command(node_instances.local)

        # TODO: consolidate with `manager` of the same type
        _cfy.add_command(inputs)
        _cfy.add_command(outputs)
        _cfy.add_command(execute)


_register_commands()


if __name__ == '__main__':
    _cfy()
