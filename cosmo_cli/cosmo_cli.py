#!/usr/bin/env python
# vim: ts=4 sw=4 et

__author__ = 'ran'

# Standard
import argparse
import json
import time
import inspect
import itertools
import socket
import os
import paramiko
import shutil
import tempfile
import logging
from scp import SCPClient

# OpenStack
import keystoneclient.v2_0.client as keystone_client
import novaclient.v1_1.client as nova_client
import neutronclient.neutron.client as neutron_client

# Project
from cosmo_rest_client.cosmo_rest_client import CosmoRestClient

EP_FLAG = 'externally_provisioned'

EXTERNAL_PORTS = (22, 8100) # SSH, REST service
INTERNAL_PORTS = (5555, 5672, 53229) # Riemann, RabbitMQ, FileServer

SSH_CONNECT_RETRIES = 5
SSH_CONNECT_SLEEP = 5

SHELL_PIPE_TO_LOGGER = ' |& logger -i -t cosmo-bootstrap -p local0.info'

class OpenStackLogicError(RuntimeError):
    pass


class CreateOrEnsureExists(object):

    def __init__(self, logger):
        self.create_or_ensure_logger = logger

    def create_or_ensure_exists(self, config, name, *args, **kw):
        # config hash is only used for 'externally_provisioned' attribute
        if 'externally_provisioned' in config and config['externally_provisioned']:
            method = 'ensure_exists'
        else:
            method = 'check_and_create'
        return getattr(self, method)(name, *args, **kw)

    def check_and_create(self, name, *args, **kw):
        self.create_or_ensure_logger.info("Will create {0} '{1}'".format(self.__class__.WHAT, name))
        if self.list_objects_with_name(name):
            raise OpenStackLogicError("{0} '{1}' already exists".format(self.__class__.WHAT, name))
        return self.create(name, *args, **kw)

    def ensure_exists(self, name, *args, **kw):
        self.create_or_ensure_logger.info("Will use existing {0} '{1}'".format(self.__class__.WHAT, name))
        ret = self.find_by_name(name)
        if not ret:
            raise OpenStackLogicError("{0} '{1}' was not found".format(self.__class__.WHAT, name))
        return ret['id']

    def find_by_name(self, name):
        matches = self.list_objects_with_name(name)

        if len(matches) == 0:
            return None
        if len(matches) == 1:
            return matches[0]
        raise OpenStackLogicError("Lookup of {0} named '{1}' failed. There are {2} matches."
        .format(self.__class__.WHAT, name, len(matches)))

    def _fail_on_missing_required_parameters(self, obj, required_parameters, hint_where):
        for k in required_parameters:
            if k not in obj:
                raise OpenStackLogicError("Required parameter '{0}' is missing (under {3}'s properties.{1}). "
                                          "Required parameters are: {2}".format(k, hint_where, required_parameters,
                                                                                self.__class__.WHAT))


class CreateOrEnsureExistsNova(CreateOrEnsureExists):

    def __init__(self, logger, connector):
        CreateOrEnsureExists.__init__(self, logger)
        self.nova_client = connector.get_nova_client()


class CreateOrEnsureExistsNeutron(CreateOrEnsureExists):

    def __init__(self, logger, connector):
        CreateOrEnsureExists.__init__(self, logger)
        self.neutron_client = connector.get_neutron_client()


class OpenStackNetworkCreator(CreateOrEnsureExistsNeutron):

    WHAT = 'network'

    def list_objects_with_name(self, name):
        return self.neutron_client.list_networks(name=name)['networks']

    def create(self, name, ext=False):
        n = {
            'network': {
                'name': name,
                'admin_state_up': True,
            }
        }
        if ext:
            n['router:external'] =  ext
        ret = self.neutron_client.create_network(n)
        return ret['network']['id']


class OpenStackSubnetCreator(CreateOrEnsureExistsNeutron):

    WHAT = 'subnet'

    def list_objects_with_name(self, name):
        return self.neutron_client.list_subnets(name=name)['subnets']

    def create(self, name, ip_version, cidr, net_id):
        ret = self.neutron_client.create_subnet({
            'subnet': {
                'name': name,
                'ip_version': ip_version,
                'cidr': cidr,
                'network_id': net_id
            }
        })
        return ret['subnet']['id']


class OpenStackRouterCreator(CreateOrEnsureExistsNeutron):

    WHAT = 'router'

    def list_objects_with_name(self, name):
        return self.neutron_client.list_routers(name=name)['routers']

    def create(self, name, interfaces=None, external_gateway_info=None):
        args = {
            'router': {
                'name': name,
                'admin_state_up': True
            }
        }
        if external_gateway_info:
            args['router']['external_gateway_info'] = external_gateway_info
        router_id = self.neutron_client.create_router(args)['router']['id']
        if interfaces:
            for i in interfaces:
                self.neutron_client.add_interface_router(router_id, i)
        return router_id


class OpenStackSecurityGroupCreator(CreateOrEnsureExistsNova):

    WHAT = 'security group'

    def list_objects_with_name(self, name):
        sgs = self.nova_client.security_groups.list()
        return [{'id': sg.id} for sg in sgs if sg.name == name]

    def create(self, name, description, rules):
        sg = self.nova_client.security_groups.create(name, description)
        for rule in rules:
            self.nova_client.security_group_rules.create(
                sg.id,
                ip_protocol="tcp",
                from_port=rule['port'],
                to_port=rule['port'],
                cidr=rule.get('cidr'),
                group_id=rule.get('group_id')
            )
        return sg.id


class OpenStackServerCreator(CreateOrEnsureExistsNova):

    WHAT = 'server'

    def list_objects_with_name(self, name):
        servers = self.nova_client.servers.list(True, {'name': name})
        return [{'id': server.id} for server in servers]

    def create(self, name, server_config, sgm_id, *args, **kwargs):
        """
        Creates a server. Exposes the parameters mentioned in
        http://docs.openstack.org/developer/python-novaclient/api/novaclient.v1_1.servers.html#novaclient.v1_1.servers.ServerManager.create
        """

        self._fail_on_missing_required_parameters(server_config, ('name', 'flavor', 'image', 'key_name'),
                                                  'nova.instance')

        # First parameter is 'self', skipping
        params_names = inspect.getargspec(self.nova_client.servers.create).args[1:]
        params_default_values = inspect.getargspec(self.nova_client.servers.create).defaults
        params = dict(itertools.izip(params_names, params_default_values))

        # Fail on unsupported parameters
        for k in server_config:
            if k not in params:
                raise ValueError("Parameter with name '{0}' must not be passed to openstack provisioner "
                                 "(under host's properties.nova.instance)".format(k))

        for k in params:
            if k in server_config:
                params[k] = server_config[k]

        server_name = server_config['name']
        if self.find_by_name(server_name):
            raise RuntimeError("Can not provision the server with name '{0}' because server with such name "
                               "already exists"
            .format(server_name))

        self.create_or_ensure_logger.info("Asking Nova to create server. Parameters: {0}".format(str(params)))

        configured_sgs = []
        if params['security_groups'] is not None:
            configured_sgs = params['security_groups']
        params['security_groups'] = [sgm_id] + configured_sgs

        server = self.nova_client.servers.create(**params)
        server = self._wait_for_server_to_become_active(server_name, server)
        return server.id

    def add_floating_ip(self, server_id, ip):
        server = self.nova_client.servers.get(server_id)
        server.add_floating_ip(ip)

    def get_server_ips_in_network(self, server_id, network_name):
        server = self.nova_client.servers.get(server_id)
        if network_name not in server.networks:
            raise OpenStackLogicError("Server {0} ({1}) does not have address in network {2}".format(server.name, server_id, network_name))
        return server.networks[network_name]

    def _wait_for_server_to_become_active(self, server_name, server):
        timeout = 100
        while server.status != "ACTIVE":
            timeout -= 5
            if timeout <= 0:
                raise RuntimeError('Server failed to start in time')
            time.sleep(5)
            server = self.nova_client.servers.get(server.id)

        return server


class OpenStackConnector(object):

    # TODO: maybe lazy?
    def __init__(self, config):
        self.config = config
        self.keystone_client = keystone_client.Client(**self.config['keystone'])

        if self.config['management']['neutron_enabled_region']:
            self.neutron_client = neutron_client.Client('2.0', endpoint_url=config['neutron']['url'],
                                                        token=self.keystone_client.auth_token)
            self.neutron_client.format = 'json'
        else:
            self.neutron_client = None

        kconf = self.config['keystone']
        self.nova_client = nova_client.Client(
            kconf['username'],
            kconf['password'],
            kconf['tenant_name'],
            kconf['auth_url'],
            region_name=self.config['management']['region'],
            http_log_debug=False
        )

    def get_keystone_client(self):
        return self.keystone_client

    def get_neutron_client(self):
        return self.neutron_client

    def get_nova_client(self):
        return self.nova_client


class CosmoOnOpenStackBootstrapper(object):
    """ Bootstraps Cosmo on OpenStack """

    def __init__(self, logger, config, network_creator, subnet_creator, router_creator, sg_creator, server_creator):
        self.logger = logger
        self.config = config
        self.network_creator = network_creator
        self.subnet_creator = subnet_creator
        self.router_creator = router_creator
        self.sg_creator = sg_creator
        self.server_creator = server_creator

    def run(self, mgmt_ip):
        if not mgmt_ip:
            mgmt_ip = self._create_topology()
        self._bootstrap_manager(mgmt_ip)
        return mgmt_ip

    def _create_topology(self):
        insconf = self.config['management']['instance']

        is_neutron_enabled_region = self.config['management']['neutron_enabled_region']
        if is_neutron_enabled_region:
            nconf = self.config['management']['network']
            net_id = self.network_creator.create_or_ensure_exists(nconf, nconf['name'])

            sconf = self.config['management']['subnet']
            subnet_id = self.subnet_creator.create_or_ensure_exists(sconf, sconf['name'], sconf['ip_version'],
                                                                    sconf['cidr'], net_id)

            enconf = self.config['management']['ext_network']
            enet_id = self.network_creator.create_or_ensure_exists(enconf, enconf['name'], ext=True)

            rconf = self.config['management']['router']
            self.router_creator.create_or_ensure_exists(rconf, rconf['name'], interfaces=[
                    {'subnet_id': subnet_id},
                ], external_gateway_info={"network_id": enet_id})

            insconf['nics'] = [
                    {'net-id': net_id},
                ]

        # Security group for Cosmo created instances
        sguconf = self.config['management']['security_group_user']
        sgu_id = self.sg_creator.create_or_ensure_exists(sguconf, sguconf['name'], 'Cosmo created machines', [])

        # Security group for Cosmo manager, allows created instances -> manager communication
        sgmconf = self.config['management']['security_group_manager']
        sg_rules = [{'port': p, 'group_id': sgu_id} for p in INTERNAL_PORTS] + \
                   [{'port': p, 'cidr': sgmconf['cidr']} for p in EXTERNAL_PORTS]
        sgm_id = self.sg_creator.create_or_ensure_exists(sgmconf, sgmconf['name'], 'Cosmo Manager', sg_rules)

        server_id = self.server_creator.create_or_ensure_exists(
            insconf,
            insconf['name'],
            {k: v for k,v in insconf.iteritems() if k != EP_FLAG},
            sgm_id if is_neutron_enabled_region else sgmconf['name'],
        )

        if is_neutron_enabled_region:
            self.logger.info('Attaching IP {0} to the instance'.format(enconf['floating_ip']))
            self.server_creator.add_floating_ip(server_id, enconf['floating_ip'])
            return enconf['floating_ip']
        else:
            return self.server_creator.get_server_ips_in_network(server_id, 'private')[1]

    def _bootstrap_manager(self, mgmt_ip):
        self.logger.info('Initializing manager on the machine at {0}'.format(mgmt_ip))
        env_config = self.config['env']
        ssh = self._create_ssh_channel_with_mgmt(mgmt_ip, env_config)
        try:
            self._copy_files_to_manager(ssh, env_config, self.config['keystone'])

            self.logger.debug('Installing required packages on manager')
            self._exec_command_on_manager(ssh, 'echo "127.0.0.1 $(cat /etc/hostname)" | sudo tee -a /etc/hosts')
            self._exec_command_on_manager(ssh, 'sudo apt-get -y -q update' + SHELL_PIPE_TO_LOGGER)
            self._exec_install_command_on_manager(ssh, 'apt-get install -y -q python-dev git rsync openjdk-7-jdk maven python-pip' + SHELL_PIPE_TO_LOGGER)
            self._exec_install_command_on_manager(ssh, 'pip install -q retrying timeout-decorator')

            # use open sdk java 7
            self._exec_command_on_manager(ssh, 'sudo update-alternatives --set java '
                                               '/usr/lib/jvm/java-7-openjdk-amd64/jre/bin/java')

            # configure and clone cosmo-manager from github
            branch = env_config['cosmo_branch']
            workingdir = '{0}/cosmo-work'.format(env_config['userhome_on_management'])
            version = env_config['cosmo_version']
            configdir = '{0}/cosmo-manager/vagrant'.format(workingdir)

            self.logger.debug('cloning cosmo on manager')
            self._exec_command_on_manager(ssh, 'mkdir -p {0}'.format(workingdir))
            self._exec_command_on_manager(ssh, 'git clone https://github.com/CloudifySource/cosmo-manager.git '
                                               '{0}/cosmo-manager'
                                               .format(workingdir))
            self._exec_command_on_manager(ssh, '( cd {0}/cosmo-manager ; git checkout {1} )'.format(workingdir, branch))

            self.logger.debug('running the manager bootstrap script remotely')
            run_script_command = 'DEBIAN_FRONTEND=noninteractive python2.7 {0}/cosmo-manager/vagrant/' \
                                 'bootstrap_lxc_manager.py --working_dir={0} --cosmo_version={1} --config_dir={2} ' \
                                 '--install_openstack_provisioner'.format(workingdir, version, configdir)
            if 'install_logstash' in env_config and env_config['install_logstash']:
                run_script_command += ' --install_logstash'
            run_script_command += ' {0}'.format(SHELL_PIPE_TO_LOGGER)
            self._exec_command_on_manager(ssh, run_script_command)

            self.logger.debug('rebuilding cosmo on manager')
        finally:
            ssh.close()

    def _create_ssh_channel_with_mgmt(self, mgmt_ip, env_config):
        ssh = paramiko.SSHClient()
        # TODO: support fingerprint in config json
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        #trying to ssh connect to management server. Using retries since it might take some time to find routes to host
        for retry in range(0, SSH_CONNECT_RETRIES):
            try:
                ssh.connect(mgmt_ip, username=env_config['user_on_management'],
                            key_filename=env_config['management_key_path'], look_for_keys=False)
                return ssh
            except socket.error:
                time.sleep(SSH_CONNECT_SLEEP)
        raise RuntimeError('Failed to ssh connect to management server')

    def _copy_files_to_manager(self, ssh, env_config, keystone_config):
        self.logger.info('Uploading files to manager')
        scp = SCPClient(ssh.get_transport())

        userhome_on_management = env_config['userhome_on_management']
        tempdir = tempfile.mkdtemp()
        try:
            scp.put(env_config['agents_key_path'], userhome_on_management + '/.ssh', preserve_times=True)
            keystone_file_path = self._make_keystone_file(tempdir, keystone_config)
            scp.put(keystone_file_path, userhome_on_management, preserve_times=True)

        finally:
            shutil.rmtree(tempdir)

    def _make_keystone_file(self, tempdir, keystone_config):
        keystone_file_path = os.path.join(tempdir, 'keystone_config.json')
        with open(keystone_file_path, 'w') as f:
            json.dump(keystone_config, f)
        return keystone_file_path

    def _exec_install_command_on_manager(self, ssh, install_command):
        command = 'DEBIAN_FRONTEND=noninteractive sudo -E {0}'.format(install_command)
        return self._exec_command_on_manager(ssh, command)

    def _exec_command_on_manager(self, ssh, command):
        self.logger.info('EXEC START: {0}'.format(command))
        chan = ssh.get_transport().open_session()
        chan.exec_command(command)
        stdin = chan.makefile('wb', -1)
        stdout = chan.makefile('rb', -1)
        stderr = chan.makefile_stderr('rb', -1)

        try:
            exit_code = chan.recv_exit_status()
            if exit_code != 0:
                errors = stderr.readlines()
                raise RuntimeError('Error occurred when trying to run a command on the management machine. command '
                                   'was: {0} ; Error(s): {1}'.format(command, errors))

            response_lines = stdout.readlines()
            self.logger.info('EXEC END: {0}'.format(command))
            return response_lines
        finally:
            stdin.close()
            stdout.close()
            stderr.close()
            chan.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger = logging.getLogger(__name__)

    # http://stackoverflow.com/questions/8144545/turning-off-logging-in-paramiko
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description='Installs Cosmo in an OpenStack environment')
    subparsers = parser.add_subparsers()

    parser_bootstrap = subparsers.add_parser('bootstrap', help='command for bootstrapping cosmo on openstack')
    parser_publish = subparsers.add_parser('publish', help='command for publishing a blueprint')
    parser_execute = subparsers.add_parser('execute', help='command for executing a deployment\'s operation')
    parser_deploy = subparsers.add_parser('deploy', help='command for creating a new deployment')

    parser_bootstrap.add_argument(
        'config_file',
        metavar='CONFIG_FILE',
        type=argparse.FileType(),
        help='Path to the cosmo configuration file'
    )
    parser_bootstrap.add_argument(
        '-management_ip',
        metavar='MANAGEMENT_IP',
        type=str,
        help='Existing machine which should cosmo management should be installed and deployed on')

    parser_bootstrap.set_defaults(handler=_bootstrap_cosmo)

    parser_publish.add_argument(
        'blueprint_path',
        metavar='BLUEPRINT_FILE',
        help="Path to the application's blueprint file",

    )
    parser_publish.add_argument(
        'management_ip',
        metavar='MANAGEMENT_IP',
        help='The cosmo management server ip address'
    )
    parser_publish.set_defaults(handler=_publish_blueprint)

    parser_execute.add_argument(
        'operation',
        metavar='OPERATION',
        choices=['install'],
        help='The operation to execute'
    )
    parser_execute.add_argument(
        'deployment_id',
        metavar='DEPLOYMENT_ID',
        help='The id of the deployment to execute the operation on'
    )
    parser_execute.add_argument(
        'management_ip',
        metavar='MANAGEMENT_IP',
        help='The cosmo management server ip address'
    )
    parser_execute.set_defaults(handler=_execute_deployment_operation)

    parser_deploy.add_argument(
        'blueprint_id',
        metavar='BLUEPRINT_ID',
        help='The blueprint id in the catalog'
    )
    parser_deploy.add_argument(
        'management_ip',
        metavar='MANAGEMENT_IP',
        help='The cosmo management server ip address'
    )
    parser_deploy.set_defaults(handler=_create_deployment)

    args = parser.parse_args()
    args.handler(logger, args)


def _bootstrap_cosmo(logger, args):
    try:
        config = json.loads(args.config_file.read())
    finally:
        args.config_file.close()

    connector = OpenStackConnector(config)
    network_creator = OpenStackNetworkCreator(logger, connector)
    subnet_creator = OpenStackSubnetCreator(logger, connector)
    router_creator = OpenStackRouterCreator(logger, connector)
    server_creator = OpenStackServerCreator(logger, connector)
    sg_creator = OpenStackSecurityGroupCreator(logger, connector)
    bootstrapper = CosmoOnOpenStackBootstrapper(logger, config, network_creator, subnet_creator, router_creator,
                                                sg_creator, server_creator)
    mgmt_ip = bootstrapper.run(args.management_ip)
    print("Management server is up at {0}".format(mgmt_ip))


def _publish_blueprint(logger, args):
    blueprint_path = args.blueprint_path
    management_ip = args.management_ip

    logger.info('Publishing blueprint {0} to management server {1}'.format(blueprint_path, management_ip))
    client = CosmoRestClient(management_ip)
    blueprint_state = client.publish_blueprint(blueprint_path)
    logger.info("Published blueprint, blueprint's id is: {0}".format(blueprint_state.id))


def _create_deployment(logger, args):
    blueprint_id = args.blueprint_id
    management_ip = args.management_ip

    logger.info('Creating new deployment from blueprint {0} at management server {1}'.format(blueprint_id,
                                                                                             management_ip))
    client = CosmoRestClient(management_ip)
    deployment = client.create_deployment(blueprint_id)
    logger.info("Deployment created, deployment's id is: {0}".format(deployment.id))


def _execute_deployment_operation(logger, args):
    deployment_id = args.deployment_id
    operation = args.operation
    management_ip = args.management_ip

    logger.info('Executing operation {0} on deployment {1} at management server {2}'.format(operation, deployment_id,
                                                                                            management_ip))

    def events_printer(events):
        for event in events:
            print(event)

    client = CosmoRestClient(management_ip)
    client.execute_deployment(deployment_id, operation, events_printer)
    logger.info("Finished executing operation {0} on deployment".format(operation))


if __name__ == '__main__':
    main()
