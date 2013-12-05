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
import tarfile
import shutil
import tempfile
from scp import SCPClient


# OpenStack
import keystoneclient.v2_0.client as keystone_client
import novaclient.v1_1.client as nova_client
import neutronclient.neutron.client as neutron_client

EP_FLAG = 'externally_provisioned'

EXTERNAL_PORTS = (22, 9000)
INTERNAL_PORTS = (5555, 5672) # Riemann, RabbitMQ


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
        ret = self.neutron_client.create_network({
            'network': {
                'name': name,
                'admin_state_up': True,
                'router:external': ext
            }
        })
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
        return self.nova_client.servers.list(True, {'name': name})

    def create(self, name, server_config, *args, **kwargs):
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

        server_info = self.nova_client.servers.create(**params)
        server_info = self._wait_for_server_to_become_active(server_name, server_info)
        # returning the public ip of the server
        return server_info.networks['private'][1]

    def _wait_for_server_to_become_active(self, server_name, server_info):
        timeout = 100
        while server_info.status != "ACTIVE":
            timeout -= 5
            if timeout <= 0:
                raise RuntimeError('Server failed to start in time')
            time.sleep(5)
            server_info = self.find_by_name(server_name)

        return server_info


class OpenStackConnector(object):

    # TODO: maybe lazy?
    def __init__(self, config):
        self.config = config
        self.keystone_client = keystone_client.Client(**self.config['keystone'])

        self.neutron_client = neutron_client.Client('2.0', endpoint_url=config['neutron']['url'],
                                                    token=self.keystone_client.auth_token)
        self.neutron_client.format = 'json'

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


class CosmoOnOpenStackInstaller(object):
    """ Installs Cosmo on OpenStack """

    def __init__(self, logger, config, network_creator, subnet_creator, router_creator, sg_creator, server_creator):
        self.logger = logger
        self.config = config
        self.network_creator = network_creator
        self.subnet_creator = subnet_creator
        self.router_creator = router_creator
        self.sg_creator = sg_creator
        self.server_creator = server_creator

    def run(self):
        nconf = self.config['management']['network']
        #net_id = self.network_creator.create_or_ensure_exists(nconf, nconf['name'])

        sconf = self.config['management']['subnet']
        # subnet_id = self.subnet_creator.create_or_ensure_exists(sconf, sconf['name'], sconf['ip_version'],
        #                                                         sconf['cidr'], net_id)

        enconf = self.config['management']['ext_network']
        # enet_id = self.network_creator.create_or_ensure_exists(enconf, enconf['name'], ext=True)

        rconf = self.config['management']['router']
        # self.router_creator.create_or_ensure_exists(rconf, rconf['name'], interfaces=[
        #     {'subnet_id': subnet_id},
        #     ], external_gateway_info={"network_id": enet_id})
        #
        # Security group for Cosmo created instances
        sguconf = self.config['management']['security_group_user']
        # sgu_id = self.sg_creator.create_or_ensure_exists(sguconf, sguconf['name'], 'Cosmo created machines', [])

        # Security group for Cosmo manager, allows created instances -> manager communication
        sgmconf = self.config['management']['security_group_manager']
        # sg_rules = [{'port': p, 'group_id': sgu_id} for p in INTERNAL_PORTS] + \
        #            [{'port': p, 'cidr': sgmconf['cidr']} for p in EXTERNAL_PORTS]
        # sgm_id = self.sg_creator.create_or_ensure_exists(sgmconf, sgmconf['name'], 'Cosmo Manager', sg_rules)

        mconf = self.config['management']
        insconf = mconf['instance']
        mgmt_ip = self.server_creator.create_or_ensure_exists(mconf, insconf['name'], insconf)

        self._bootstrap_manager(mgmt_ip)

    def _bootstrap_manager(self, mgmt_ip):
        self.logger.debug()
        env_config = self.config['env']
        ssh = self._create_ssh_channel_with_mgmt(mgmt_ip, env_config)
        try:
            self._copy_files_to_manager(ssh, env_config, self.config['keystone'])

            # installing required packages to run bootstrap_lxc_manager
            self._exec_command_on_manager(ssh, 'sudo apt-get -y -q update')
            self._exec_install_command_on_manager(ssh, 'apt-get install -y -q python-dev git rsync openjdk-7-jdk maven')
            self._exec_install_command_on_manager(ssh, 'apt-get install -y -q python-pip')
            self._exec_install_command_on_manager(ssh, 'pip install -q retrying')
            self._exec_install_command_on_manager(ssh, 'pip install -q timeout-decorator')

            # use open sdk java 7
            self._exec_command_on_manager(ssh, 'sudo update-alternatives --set java '
                                               '/usr/lib/jvm/java-7-openjdk-amd64/jre/bin/java')

            # configure and clone cosmo-manager from github
            branch = 'develop'
            workingdir = '{0}/cosmo-work'.format(env_config['userhome_on_management'])
            version = '0.1-SNAPSHOT'
            configdir = '{0}/cosmo-manager/vagrant'.format(workingdir)

            self._exec_command_on_manager(ssh, 'mkdir -p {0}'.format(workingdir))
            # cloning and selecting branch
            self._exec_command_on_manager(ssh, 'git clone https://github.com/CloudifySource/cosmo-manager.git '
                                               '{0}/cosmo-manager'
            .format(workingdir))
            self._exec_command_on_manager(ssh, '( cd {0}/cosmo-manager ; git checkout {1} )'.format(workingdir, branch))

            # bootstrap the machine as a management machine
            self._exec_command_on_manager(ssh, 'DEBIAN_FRONTEND=noninteractive python2.7 {0}/cosmo-manager/vagrant/'
                                               'bootstrap_lxc_manager.py --working_dir={0} --cosmo_version={1} '
                                               '--config_dir={2} --install_openstack_provisioner --install_logstash'
            .format(workingdir, version, configdir))

            self._exec_command_on_manager(ssh, 'mvn -q clean package -DskipTests -Pall -f '
                                               '{0}/cosmo-manager/orchestrator/pom.xml'
            .format(workingdir))
            self._exec_command_on_manager(ssh, 'rm {0}/cosmo.jar'.format(workingdir))
            self._exec_command_on_manager(ssh, 'cp {0}/cosmo-manager/orchestrator/target/cosmo.jar {0}'.format(
                workingdir))
        finally:
            ssh.close()

    def _create_ssh_channel_with_mgmt(self, mgmt_ip, env_config):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        #trying to ssh connect to management server. Using retries since it might take some time to find routes to host
        retries = 5
        while retries > 0:
            try:
                ssh.connect(mgmt_ip, username=env_config['user_on_management'],
                            key_filename=env_config['management_key_path'], look_for_keys=False)
                return ssh
            except socket.error:
                retries -= 1
                time.sleep(5)
        raise RuntimeError('Failed to ssh connect to management server')

    def _copy_files_to_manager(self, ssh, env_config, keystone_config):
        scp = SCPClient(ssh.get_transport())

        userhome_on_management = env_config['userhome_on_management']
        workdir = env_config['workdir']

        tempdir = tempfile.mkdtemp()
        try:
            scp.put(env_config['agents_key_path'], userhome_on_management + '/.ssh', preserve_times=True)
            keystone_file_path = self._make_keystone_file(tempdir, keystone_config)
            scp.put(keystone_file_path, userhome_on_management, preserve_times=True)

            runtime_dir = os.getcwd()
            os.chdir(workdir)
            try:
                app_name = os.path.basename(workdir)
                tar_name = '{0}.tar.gz'.format(app_name)
                tar_path = os.path.join('{0}'.format(tempdir), tar_name)
                tar = tarfile.open(tar_path, 'w:gz')
                try:
                    tar.add(workdir, arcname=app_name)
                finally:
                    tar.close()
                scp.put(tar_path, userhome_on_management, preserve_times=True)
                self._exec_command_on_manager(ssh, 'tar xzvf {0}/{1}'.format(userhome_on_management, tar_name))
            finally:
                os.chdir(runtime_dir)
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
            return response_lines
        finally:
            stdin.close()
            stdout.close()
            stderr.close()
            chan.close()


def main():
    parser = argparse.ArgumentParser(description='Installs Cosmo in an OpenStack environment')
    parser.add_argument(
        'config_file_path',
        metavar='CONFIG_FILE',
        help='Path to the cosmo configuration file'
    )
    args = parser.parse_args()

    with open(args.config_file_path) as f:
        config = json.loads(f.read())

    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    connector = OpenStackConnector(config)
    network_creator = OpenStackNetworkCreator(logger, connector)
    subnet_creator = OpenStackSubnetCreator(logger, connector)
    router_creator = OpenStackRouterCreator(logger, connector)
    server_creator = OpenStackServerCreator(logger, connector)
    sg_creator = OpenStackSecurityGroupCreator(logger, connector)
    installer = CosmoOnOpenStackInstaller(logger, config, network_creator, subnet_creator, router_creator, sg_creator,
                                          server_creator)
    installer.run()


if __name__ == '__main__':
    main()