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
# from . import utils
from .config import cfy

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
from .commands import inputs
from .commands import outputs
from .commands import execute
from .commands import recover
from .commands import plugins
from .commands import upgrade
from .commands import install
from .commands import teardown
from .commands import rollback
from .commands import profiles
from .commands import workflows
from .commands import uninstall
from .commands import snapshots
from .commands import bootstrap
from .commands import blueprints
from .commands import executions
from .commands import deployments
from .commands import node_instances
from .commands import install_plugins
from .commands import maintenance_mode
from .commands import create_requirements


@cfy.group(name='cfy')
@cfy.options.verbose_exposed
@cfy.options.version
def _cfy(verbose):
    """Cloudify's Command Line Interface

    Note that some commands are only available if you're using a manager.
    You can use a manager by running the `cfy use` command and providing
    it with the IP of your manager (and ssh credentials if applicable).

    To activate bash-completion. Run: `eval "$(_CFY_COMPLETE=source cfy)"`

    Cloudify's working directory resides in ~/.cloudify. To change it, set
    the variable `CFY_WORKDIR` to something else (e.g. /tmp/).
    """
    # TODO: Multiple blueprints and deloyments:
    # In the "local" profile, create a directory per blueprint and in it
    # an id per deployment.
    # `cfy init BLUEPRINT_PATH` will initalize a directory for the blueprint
    # and within it a folder for that deployment. If a user wants to switch
    # to another blueprint: `cfy use BLUEPRINT_ID`. If they want to switch
    # to a particular deployment, `cfy use BLUEPRINT_ID -d DEPLOYMENT_ID`

    logger.configure_loggers()
    # cfy.set_cli_except_hook(verbose)


def _register_commands():
    """Register the CLI's commands.

    Here is where we decide which commands register with the cli
    and which don't. We should decide that according to whether
    a manager is currently `use`d or not.
    """
    # TODO: decide whether all commands are registered or not.
    # is_manager_active = utils.is_manager_active()

    _cfy.add_command(use.use)
    _cfy.add_command(init.init)
    _cfy.add_command(recover.recover)
    _cfy.add_command(profiles.profiles)
    _cfy.add_command(bootstrap.bootstrap)
    _cfy.add_command(create_requirements.create_requirements)

    # TODO: Instead of manually stating each module,
    # we might want to try importing all modules in the `commands`
    # package recursively and check if they have a certain attribute
    # which indicates they belong to `manager`.
    # if is_manager_active:
    _cfy.add_command(dev.dev)
    _cfy.add_command(ssh.ssh)
    _cfy.add_command(logs.logs)
    _cfy.add_command(agents.agents)
    _cfy.add_command(events.events)
    _cfy.add_command(status.status)
    _cfy.add_command(upgrade.upgrade)
    _cfy.add_command(install.manager)
    _cfy.add_command(uninstall.manager)
    _cfy.add_command(teardown.teardown)
    _cfy.add_command(rollback.rollback)
    _cfy.add_command(snapshots.snapshots)
    _cfy.add_command(node_instances.manager)
    _cfy.add_command(maintenance_mode.maintenance_mode)

    # TODO: consolidate with `local` of the same type
    _cfy.add_command(nodes.nodes)
    _cfy.add_command(groups.groups)
    _cfy.add_command(plugins.plugins)
    _cfy.add_command(workflows.workflows)
    _cfy.add_command(blueprints.blueprints)
    _cfy.add_command(executions.executions)
    _cfy.add_command(deployments.deployments)

    # else:
    _cfy.add_command(install.local)
    _cfy.add_command(uninstall.local)
    _cfy.add_command(node_instances.local)
    _cfy.add_command(install_plugins.install_plugins)

    # TODO: consolidate with `manager` of the same type
    _cfy.add_command(inputs.inputs)
    _cfy.add_command(outputs.outputs)
    _cfy.add_command(execute.execute)


_register_commands()


if __name__ == '__main__':
    _cfy()
