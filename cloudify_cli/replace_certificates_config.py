########
# Copyright (c) 2020 Cloudify.co Ltd. All rights reserved
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

from os.path import expanduser
from socket import error as socket_error

from retrying import retry

from cloudify_cli import env
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.logger import get_global_verbosity

try:
    from fabric import Connection
    from paramiko import AuthenticationException
except ImportError:
    Connection = None
    AuthenticationException = None


NEW_CERTS_TMP_DIR_PATH = '/tmp/new_cloudify_certs/'


class Node(object):
    def __init__(self,
                 host_ip,
                 node_type,
                 node_dict,
                 logger):
        self.host_ip = host_ip
        self.node_type = node_type
        self.username = env.profile.ssh_user
        self.key_file_path = env.profile.ssh_key
        self.node_dict = node_dict
        self.errors_list = []
        self.logger = logger

    def _get_connection(self):
        connection = Connection(
            host=self.host_ip, user=self.username, port=22,
            connect_kwargs={'key_filename': self.key_file_path})
        try:  # Connection is lazy, so **we** need to check it can be opened
            connection.open()
        except (socket_error, AuthenticationException) as exc:
            raise CloudifyCliError(
                "SSH: could not connect to {host} (username: {user}, "
                "key: {key}): {exc}".format(
                    host=self.host_ip, user=self.username,
                    key=self.key_file_path, exc=exc))
        finally:
            connection.close()

        return connection

    def run_command(self, command):
        with self._get_connection() as connection:
            self.logger.debug('Running `%s` on %s', command, self.host_ip)
            hide = 'both' if get_global_verbosity() == 0 else 'stderr'
            result = connection.run(command, warn=True, hide=hide)
            if result.failed:
                if hide == 'both':  # No logs are shown
                    raise CloudifyCliError(
                        'The command `{0}` on host {1} failed with the '
                        'error {2}'.format(command, self.host_ip,
                                           result.stderr))
                raise CloudifyCliError()

    def put_file(self, local_path, remote_path):
        with self._get_connection() as connection:
            self.logger.debug('Copying %s to %s on host %a',
                              local_path, remote_path, self.host_ip)
            connection.put(expanduser(local_path), remote_path)

    def replace_certificates(self):
        self.logger.info('Replacing certificates on host %s [%s]',
                         self.host_ip, self.node_type)
        command = self._append_verbose('cfy_manager certificates replace')
        self.run_command(command)
        self.run_command('rm -rf {0}'.format(NEW_CERTS_TMP_DIR_PATH))

    def validate_certificates(self):
        self.logger.info('Validating certificates on host %s [%s]',
                         self.host_ip, self.node_type)
        self._pass_certificates()
        command = self._append_verbose(
            'cfy_manager certificates replace --only-validate')
        self.run_command(command)

    @staticmethod
    def _append_verbose(command):
        if get_global_verbosity() > 1:
            command += ' -v'
        return command

    def _pass_certificates(self):
        self._prepare_new_certs_dir()
        for cert_name, new_cert_path in self.node_dict.items():
            self.put_file(new_cert_path, self._get_remote_cert_path(cert_name))

    def _get_remote_cert_path(self, cert_name):
        if (self.node_type == 'manager') or ('prometheus' in cert_name):
            return NEW_CERTS_TMP_DIR_PATH + cert_name + '.pem'
        new_cert_path = 'new_' + self.node_type + '_' + cert_name[4:]
        return NEW_CERTS_TMP_DIR_PATH + new_cert_path + '.pem'

    def _prepare_new_certs_dir(self):
        self.run_command('rm -rf {0}; mkdir {0}'.format(
            NEW_CERTS_TMP_DIR_PATH))


class ReplaceCertificatesConfig(object):
    def __init__(self, config_dict, is_all_in_one, client, logger):
        if Connection is None:
            raise CloudifyCliError('SSH not available - fabric not installed')

        self.client = client
        self.logger = logger
        self.config_dict = config_dict
        self.is_all_in_one = is_all_in_one
        self.username = env.profile.ssh_user
        self.key_file_path = env.profile.ssh_key
        self.relevant_nodes_dict = {'manager': [],
                                    'postgresql_server': [],
                                    'rabbitmq': []}
        if is_all_in_one:
            self._create_all_in_one_node()
        else:
            self._create_nodes()
        self.needs_to_replace_certificates = len(self.relevant_nodes) > 0

    @property
    def relevant_nodes(self):
        relevant_nodes = []
        for instance_name in 'postgresql_server', 'rabbitmq', 'manager':
            relevant_nodes.extend(self.relevant_nodes_dict[instance_name])
        return relevant_nodes

    def validate_certificates(self):
        self.logger.info('Validating status is healthy')
        self._validate_status_ok()
        for node in self.relevant_nodes:
            node.validate_certificates()

    def replace_certificates(self):
        self.logger.info('Replacing certificates...')
        # Passing a bundle of the old+new CA certs to the agents
        self._pass_new_ca_certs_to_agents(bundle=True)
        for node in self.relevant_nodes:
            node.replace_certificates()

        self._handle_new_ca_certs()
        # Passing only the new CA cert to the agents
        self._pass_new_ca_certs_to_agents(bundle=False)
        self.logger.info('Validating status is healthy')
        self._validate_status_ok()
        self.logger.info('Successfully replaced certificates')

    def _handle_new_ca_certs(self):
        """Replace the CLI and client CA certs"""
        if env.profile.rest_certificate:
            new_manager_ca = self.config_dict['manager'].get('new_ca_cert')
            if new_manager_ca:
                expanded_path = expanduser(new_manager_ca)
                env.profile.rest_certificate = expanded_path
                env.profile.save()
                self.client = env.get_rest_client(rest_cert=expanded_path)

    # The services might take time to update
    @retry(stop_max_attempt_number=30, wait_fixed=2000)
    def _validate_status_ok(self):
        status = (self.client.manager.get_status() if self.is_all_in_one
                  else self.client.cluster_status.get_status())
        if status.get('status') != 'OK':
            raise CloudifyCliError('Cannot proceed, status is not healthy: '
                                   '{0}'.format(status))

    def _needs_to_update_agents(self):
        return (self.config_dict['manager'].get('new_ca_cert') or
                self.config_dict['rabbitmq'].get('new_ca_cert'))

    def _pass_new_ca_certs_to_agents(self, bundle):
        if not self._needs_to_update_agents():
            return
        self.logger.info('Passing CA certs to agents')
        new_manager_ca_cert = self.config_dict['manager'].get('new_ca_cert')
        new_broker_ca_cert = (new_manager_ca_cert if self.is_all_in_one else
                              self.config_dict['rabbitmq'].get('new_ca_cert'))
        self.client.agents.replace_ca_certs(bundle,
                                            new_manager_ca_cert,
                                            new_broker_ca_cert)

    def _create_all_in_one_node(self):
        node_dict = self._create_all_in_one_node_dict()
        if node_dict:
            new_node = Node(
                env.profile.manager_ip,
                'manager',
                node_dict,
                self.logger
            )
            self.relevant_nodes_dict['manager'].append(new_node)

    def _create_all_in_one_node_dict(self):
        node_dict = {}
        for instance_name in ['manager', 'postgresql_server', 'rabbitmq']:
            instance_section = self.config_dict[instance_name]
            for cert_name, cert_path in instance_section.items():
                if cert_path:
                    node_dict[cert_name] = cert_path

        return node_dict

    def _create_nodes(self):
        for instance_type, instance_dict in self.config_dict.items():
            for node in instance_dict['cluster_members']:
                node_dict = self._create_node_dict(node, instance_type)
                if node_dict:
                    new_node = Node(
                        node.get('host_ip'),
                        instance_type,
                        node_dict,
                        self.logger
                    )
                    self.relevant_nodes_dict[instance_type].append(new_node)

    def _create_node_dict(self, node, instance_type):
        node_dict = {}
        for cert_name, cert_path in node.items():
            if (cert_name == 'host_ip') or (not cert_path):
                continue
            node_dict[cert_name] = cert_path

        for ca_cert, ca_path in self.config_dict[instance_type].items():
            if (ca_cert == 'cluster_members') or (not ca_path):
                continue
            node_dict[ca_cert] = ca_path

        if instance_type == 'manager':
            postgresql_ca_cert = self.config_dict['postgresql_server'].get(
                'new_ca_cert')
            if postgresql_ca_cert:
                node_dict['new_postgresql_server_ca_cert'] = postgresql_ca_cert

            rabbit_config = self.config_dict['rabbitmq']
            rabbitmq_ca_cert = rabbit_config.get('new_ca_cert')
            if rabbitmq_ca_cert:
                node_dict['new_rabbitmq_ca_cert'] = rabbitmq_ca_cert

            # deal with 3-node cluster:
            rabbit_cluster_members = rabbit_config.get('cluster_members')
            if rabbit_cluster_members:
                mgr_rabbit = [r for r in rabbit_cluster_members
                              if r['host_ip'] == node['host_ip']]
                if mgr_rabbit:
                    node_dict['new_rabbitmq_cert'] = mgr_rabbit[0]['new_cert']
                    node_dict['new_rabbitmq_key'] = mgr_rabbit[0]['new_key']

        return node_dict
