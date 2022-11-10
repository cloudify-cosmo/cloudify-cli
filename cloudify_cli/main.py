import click
import importlib

from cloudify_cli import env
from cloudify_cli.cli import cfy


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
    import_spec=('cloudify_cli.commands.blueprints', 'blueprints'),
    short_help="Handle blueprints on the manager"
)
def manager_blueprints():
    pass


@click.group(
    name='blueprints',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.blueprints', 'local_blueprints'),
    short_help="Handle local blueprints"
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


@click.group(
    name='idp',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.idp', 'idp'),
    short_help='Identity provider commands'
)
def idp():
    pass


@click.group(
    name='ldap',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.ldap', 'ldap'),
    short_help='Set LDAP authenticator'
)
def ldap():
    pass


@click.group(
    name='users',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.users', 'users'),
    short_help='Handle Cloudify users'
)
def users():
    pass


@click.group(
    name='agents',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.agents', 'agents'),
    short_help="Handle a deployment's agents"
)
def agents():
    pass


@click.group(
    name='events',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.events', 'events'),
    short_help="Show events from workflow executions"
)
def events():
    pass


@click.group(
    name='cluster',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.cluster', 'cluster'),
    short_help="Handle the Cloudify Manager cluster (Premium feature)"
)
def cluster():
    pass


@click.group(
    name='managers',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.cluster', 'managers'),
    short_help="Handle the Cloudify Manager cluster's nodes"
)
def cluster_managers():
    pass


@click.group(
    name='db-nodes',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.cluster', 'db_nodes'),
    short_help="Handle the Cloudify DB cluster's nodes"
)
def cluster_db_nodes():
    pass


@click.group(
    name='plugins',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.plugins', 'plugins'),
    short_help="Handle plugins on the manager"
)
def plugins():
    pass


@click.group(
    name='tenants',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.tenants', 'tenants'),
    short_help="Handle Cloudify tenants (Premium feature)"
)
def tenants():
    pass


@click.group(
    name='snapshots',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.snapshots', 'snapshots'),
    short_help="Handle manager snapshots"
)
def snapshots():
    pass


@click.group(
    name='log-bundles',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.log_bundles', 'log_bundles'),
    short_help="Handle manager log bundles"
)
def log_bundles():
    pass


@click.group(
    name='user-groups',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.user_groups', 'user_groups'),
    short_help="Handle Cloudify user groups (Premium feature)"
)
def user_groups():
    pass


@click.group(
    name='maintenance-mode',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.maintenance_mode', 'maintenance_mode'),
    short_help="Handle the manager's maintenance-mode"
)
def maintenance_mode():
    pass


@click.group(
    name='secrets',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.secrets', 'secrets'),
    short_help="Handle Cloudify secrets (key-value pairs)"
)
def secrets():
    pass


@click.group(
    name='tokens',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.tokens', 'tokens'),
    short_help="Returns a valid REST token from the Cloudify Manager"
)
def tokens():
    pass


@click.group(
    name='nodes',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.nodes', 'nodes'),
    short_help="Handle a deployment's nodes"
)
def nodes():
    pass


@click.group(
    name='groups',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.groups', 'groups'),
    short_help="Handle deployment scaling groups"
)
def groups():
    pass


@click.group(
    name='workflows',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.workflows', 'workflows'),
    short_help="Handle deployment workflows"
)
def workflows():
    pass


@click.group(
    name='executions',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.executions', 'executions'),
    short_help="Handle workflow executions"
)
def manager_executions():
    pass


@click.group(
    name='executions',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.executions', 'local_executions'),
    short_help="Handle workflow executions"
)
def local_executions():
    pass


@click.group(
    name='deployments',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.deployments', 'deployments'),
    short_help="Handle deployments on the Manager"
)
def manager_deployments():
    pass


@click.group(
    name='deployments',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.deployments', 'local_deployments'),
    short_help="Handle local deployments"
)
def local_deployments():
    pass


@click.group(
    name='license',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.license', 'license'),
    short_help="Handle Cloudify licenses"
)
def license():
    pass


@click.group(
    name='sites',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.sites', 'sites'),
    short_help="Handle Cloudify sites"
)
def sites():
    pass


@click.group(
    name='certificates',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.certificates', 'certificates'),
    short_help="Handle certificates related procedures"
)
def certificates():
    pass


@click.command(
    name='apply',
    cls=LazyLoadedCommand,
    import_spec=('cloudify_cli.commands.apply', 'apply'),
    short_help='Install a blueprint or update an existing deployment '
               'with a new blueprint [manager only]'
)
def apply():
    pass


@click.group(
    name='auditlog',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.audit_log', 'auditlog'),
    short_help="Manage the audit log"
)
def auditlog():
    pass


@click.group(
    name='config',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.config', 'config'),
    short_help="Handle manager configuration"
)
def config():
    pass


@click.group(
    name='node-instances',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.node_instances', 'node_instances'),
    short_help="Handle a deployment's node-instances"
)
def manager_node_instances():
    pass


@click.command(
    name='node-instances',
    cls=LazyLoadedCommand,
    import_spec=('cloudify_cli.commands.node_instances', 'local'),
    short_help='Display node-instances for the execution'
)
def local_node_instances():
    pass


@click.group(
    name='permissions',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.permissions', 'permissions'),
    short_help="Handle manager user permissions"
)
def permissions():
    pass


@click.group(
    name='community',
    cls=LazyLoadedGroup,
    import_spec=('cloudify_cli.commands.community', 'community'),
    short_help="Commands specific for the Community edition"
)
def community():
    pass


@click.command(
    name='install',
    cls=LazyLoadedCommand,
    import_spec=('cloudify_cli.commands.install', 'manager'),
    short_help='Install an application blueprint [manager only]'
)
def manager_install():
    pass


@click.command(
    name='install',
    cls=LazyLoadedCommand,
    import_spec=('cloudify_cli.commands.install', 'local'),
    short_help='Install an application'
)
def local_install():
    pass


@click.command(
    name='uninstall',
    cls=LazyLoadedCommand,
    import_spec=('cloudify_cli.commands.uninstall', 'manager'),
    short_help='Uninstall an application via the manager'
)
def manager_uninstall():
    pass


@click.command(
    name='uninstall',
    cls=LazyLoadedCommand,
    import_spec=('cloudify_cli.commands.uninstall', 'local'),
    short_help='Uninstall an application'
)
def local_uninstall():
    pass


def _make_cfy():
    """Make the commandline click app object

    Create the app object and register all the commands on it, based on
    the current profile.
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

    _cfy.add_command(init)
    _cfy.add_command(status)
    _cfy.add_command(profiles)

    _cfy.add_command(idp)
    _cfy.add_command(ldap)
    _cfy.add_command(users)
    _cfy.add_command(agents)
    _cfy.add_command(events)
    _cfy.add_command(cluster)
    _cfy.add_command(cluster_managers)
    _cfy.add_command(cluster_db_nodes)
    _cfy.add_command(plugins)
    _cfy.add_command(tenants)
    _cfy.add_command(snapshots)
    _cfy.add_command(log_bundles)
    _cfy.add_command(user_groups)
    _cfy.add_command(maintenance_mode)
    _cfy.add_command(secrets)
    _cfy.add_command(tokens)
    _cfy.add_command(nodes)
    _cfy.add_command(groups)
    _cfy.add_command(workflows)
    _cfy.add_command(license)
    _cfy.add_command(sites)
    _cfy.add_command(certificates)
    _cfy.add_command(apply)
    _cfy.add_command(auditlog)
    _cfy.add_command(community)

    if env.is_manager_active():
        _cfy.add_command(manager_blueprints)
        _cfy.add_command(manager_deployments)
        _cfy.add_command(manager_executions)
        _cfy.add_command(manager_node_instances)
        _cfy.add_command(config)
        _cfy.add_command(permissions)
        _cfy.add_command(manager_install)
        _cfy.add_command(manager_uninstall)

    else:
        _cfy.add_command(local_blueprints)
        _cfy.add_command(local_deployments)
        _cfy.add_command(local_executions)
        _cfy.add_command(local_node_instances)
        _cfy.add_command(local_install)
        _cfy.add_command(local_uninstall)

    return _cfy


_cfy = _make_cfy()


if __name__ == '__main__':
    _cfy()
