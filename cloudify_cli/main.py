import click
import importlib

from . import env
from .cli import cfy
from .commands import ssh
from .commands import idp
from .commands import logs
from .commands import ldap
from .commands import users
from .commands import nodes
from .commands import sites
from .commands import apply
from .commands import agents
from .commands import events
from .commands import groups
from .commands import tokens
from .commands import config
from .commands import cluster
from .commands import install
from .commands import plugins
from .commands import tenants
from .commands import secrets
from .commands import license
from .commands import snapshots
from .commands import uninstall
from .commands import workflows
from .commands import executions
from .commands import permissions
from .commands import user_groups
from .commands import deployments
from .commands import certificates
from .commands import node_instances
from .commands import maintenance_mode
from .commands import audit_log


class LazyLoadedCommand(click.Command):
    def __init__(self, import_spec, **kwargs):
        super(LazyLoadedCommand, self).__init__(**kwargs)
        self._import_spec = import_spec
        self._command = None

    def _get_command(self):
        if self._command is None:
            module_name, group_name = self._import_spec
            module = importlib.import_module(module_name)
            self._command = getattr(module, group_name)
        return self._command

    def invoke(self, *a, **kw):
        return self._get_command().invoke(*a, **kw)

    def get_usage(self, *a, **kw):
        return self._get_command().get_usage(*a, **kw)

    def get_help(self, *a, **kw):
        return self._get_command().get_help(*a, **kw)

    def get_params(self, *a, **kw):
        return self._get_command().get_params(*a, **kw)


class LazyLoadedGroup(click.Group):
    def __init__(self, import_spec, **kwargs):
        super(LazyLoadedGroup, self).__init__(**kwargs)
        self._import_spec = import_spec
        self._group = None

    def _get_group(self):
        if self._group is None:
            module_name, group_name = self._import_spec
            module = importlib.import_module(module_name)
            self._group = getattr(module, group_name)
        return self._group

    def get_command(self, *a, **kw):
        return self._get_group().get_command(*a, **kw)

    def list_commands(self, *a, **kw):
        return self._get_group().list_commands(*a, **kw)

    def invoke(self, *a, **kw):
        return self._get_group().invoke(*a, **kw)

    def get_usage(self, *a, **kw):
        return self._get_group().get_usage(*a, **kw)

    def get_help(self, *a, **kw):
        return self._get_group().get_help(*a, **kw)

    def get_params(self, *a, **kw):
        return self._get_group().get_params(*a, **kw)


@click.group(
    name='blueprints',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.blueprints', 'blueprints')
)
def manager_blueprints():
    pass


@click.group(
    name='blueprints',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.blueprints', 'local_blueprints')
)
def local_blueprints():
    pass


@click.command(
    name='init',
    cls=LazyLoadedCommand,
    short_help='Initialize a working env',
    import_spec=('cloudify_cli.commands.init', 'init'),
)
def init():
    pass


@click.command(
    name='status',
    cls=LazyLoadedCommand,
    short_help='Show manager status ',
    import_spec=('cloudify_cli.commands.status', 'status'),
)
def status():
    pass


@click.group(
    name='profiles',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.profiles', 'profiles'),
    short_help='Handle Cloudify CLI profiles'
)
def profiles():
    pass


def _make_cfy():
    """Register the CLI's commands.

    Here is where we decide which commands register with the cli
    and which don't. We should decide that according to whether
    a manager is currently `use`d or not.
    """
    @cfy.group(name='cfy')
    @cfy.options.verbose(expose_value=True)
    @cfy.options.json
    @cfy.options.version
    @cfy.options.extended_view
    def _cfy(verbose):
        """Cloudify's Command Line Interface

        Note that some commands are only available if you're using a manager.
        You can use a manager by running the `cfy profiles use` command and
        providing it with the IP of your manager (and ssh credentials if
        applicable).

        To activate bash-completion. Run: `eval "$(_CFY_COMPLETE=source cfy)"`

        Cloudify's working directory resides in ~/.cloudify. To change it, set
        the variable `CFY_WORKDIR` to something else (e.g. /tmp/).
        """
        cfy.set_cli_except_hook(verbose)

    # Manager agnostic commands
    _cfy.add_command(init)
    _cfy.add_command(status)
    _cfy.add_command(profiles)

    # Manager only commands
    _cfy.add_command(ssh.ssh)
    _cfy.add_command(idp.idp)
    _cfy.add_command(logs.logs)
    _cfy.add_command(ldap.ldap)
    _cfy.add_command(users.users)
    _cfy.add_command(agents.agents)
    _cfy.add_command(events.events)
    _cfy.add_command(cluster.cluster)
    _cfy.add_command(cluster.managers)
    _cfy.add_command(cluster.db_nodes)
    _cfy.add_command(plugins.plugins)
    _cfy.add_command(tenants.tenants)
    _cfy.add_command(snapshots.snapshots)
    _cfy.add_command(user_groups.user_groups)
    _cfy.add_command(maintenance_mode.maintenance_mode)
    _cfy.add_command(secrets.secrets)
    _cfy.add_command(tokens.tokens)
    _cfy.add_command(nodes.nodes)
    _cfy.add_command(groups.groups)
    _cfy.add_command(workflows.workflows)

    _cfy.add_command(executions.executions)
    _cfy.add_command(deployments.deployments)
    _cfy.add_command(license.license)
    _cfy.add_command(sites.sites)
    _cfy.add_command(certificates.certificates)
    _cfy.add_command(apply.apply)
    _cfy.add_command(audit_log.auditlog)

    deployments.deployments.add_command(deployments.manager_create)
    deployments.deployments.add_command(deployments.manager_delete)
    deployments.deployments.add_command(deployments.manager_update)
    deployments.deployments.add_command(deployments.manager_list)
    deployments.deployments.add_command(deployments.manager_history)
    deployments.deployments.add_command(deployments.manager_get_update)
    deployments.deployments.add_command(deployments.manager_set_visibility)
    deployments.deployments.add_command(deployments.manager_set_site)
    deployments.deployments.add_command(deployments.schedule)

    executions.executions.add_command(executions.manager_cancel)

    license.license.add_command(license.environments)

    # Commands which should be both in manager and local context
    # But change depending on the context.
    if env.is_manager_active():
        _cfy.add_command(manager_blueprints)

        _cfy.add_command(config.config)
        _cfy.add_command(install.manager)
        _cfy.add_command(uninstall.manager)
        _cfy.add_command(node_instances.node_instances)
        _cfy.add_command(permissions.permissions)

        deployments.deployments.add_command(deployments.manager_inputs)
        deployments.deployments.add_command(deployments.manager_outputs)
        deployments.deployments.add_command(deployments.manager_capabilities)

        executions.executions.add_command(executions.manager_start)
        executions.executions.add_command(executions.manager_list)
        executions.executions.add_command(executions.manager_get)

        executions.executions.add_command(executions.manager_resume)
    else:
        _cfy.add_command(local_blueprints)
        _cfy.add_command(install.local)
        _cfy.add_command(uninstall.local)
        _cfy.add_command(node_instances.local)

        deployments.deployments.add_command(deployments.local_inputs)
        deployments.deployments.add_command(deployments.local_outputs)

        executions.executions.add_command(executions.local_start)
        executions.executions.add_command(executions.local_list)
        executions.executions.add_command(executions.local_get)

    return _cfy

_cfy = _make_cfy()


if __name__ == '__main__':
    _cfy()
