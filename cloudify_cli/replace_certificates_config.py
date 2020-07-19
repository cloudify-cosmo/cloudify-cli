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

from . import env
from .exceptions import CloudifyCliError

try:
    from fabric import Connection
    from paramiko import AuthenticationException
except ImportError:
    Connection = None


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
        self.connection = self._create_connection()
        self.node_dict = node_dict
        self.errors_list = []
        self.logger = logger

    def _create_connection(self):
        try:
            return Connection(
                host=self.host_ip, user=self.username, port=22,
                connect_kwargs={'key_filename': self.key_file_path})

        except AuthenticationException as e:
            self.errors_list.append(
                "SSH: could not connect to {host} "
                "(username: {user}, key: {key}): {exc}".format(
                    host=self.host_ip, user=self.username,
                    key=self.key_file_path, exc=e))

    def run_command(self, command):
        self.logger.debug('Running `%s` on %s', command, self.host_ip)
        result = self.connection.run(command, warn=True, hide='stderr')
        if result.failed:
            self._command_failed(command, result.stderr)

    def put_file(self, local_path, remote_path):
        self.logger.debug('Copying %s to %s on host %a',
                          local_path, remote_path, self.host_ip)
        self.connection.put(local_path, remote_path)

    def _command_failed(self, command, err_msg):
        err_list = [str(err) for err in err_msg.split('\n') if err]
        self.errors_list.append(
            'The command `{0}` on host {1} failed with the error(s): '
            '{2}'.format(command, self.host_ip, err_list))

    def replace_certificates(self):
        self.logger.info('Replacing certificates on host %s', self.host_ip)
        self.run_command('cfy_manager replace-certificates')
        self.run_command('rm -rf {0}'.format(NEW_CERTS_TMP_DIR_PATH))

    def validate_certificates(self):
        self.logger.info('Validating certificates on host %s', self.host_ip)
        self._pass_certificates()
        self.run_command('cfy_manager replace-certificates --only-validate')

    def _pass_certificates(self):
        self._prepare_new_certs_dir()
        for cert_name, new_cert_path in self.node_dict.items():
            self.put_file(new_cert_path, self._get_remote_cert_path(cert_name))

    def _get_remote_cert_path(self, cert_name):
        new_cert_path = (('new_' + self.node_type + '_' + cert_name[4:])
                         if self.node_type in ('postgresql_server', 'rabbitmq')
                         else cert_name)
        return NEW_CERTS_TMP_DIR_PATH + new_cert_path + '.pem'

    def _prepare_new_certs_dir(self):
        self.run_command('rm -rf {0}; mkdir {0}'.format(
            NEW_CERTS_TMP_DIR_PATH))


class ReplaceCertificatesConfig(object):
    def __init__(self, config_dict, is_all_in_one, logger):
        if Connection is None:
            raise CloudifyCliError("SSH not available - fabric not installed")

        self.logger = logger
        self.is_all_in_one = is_all_in_one
        self.config_dict = config_dict
        self.username = env.profile.ssh_user
        self.key_file_path = env.profile.ssh_key
        self.relevant_nodes_dict = {'manager': [],
                                    'postgresql_server': [],
                                    'rabbitmq': []}
        self._create_nodes()
        self.needs_to_replace_certificates = len(self.relevant_nodes) > 0

    @property
    def relevant_nodes(self):
        relevant_nodes = []
        for instance_name in 'postgresql_server', 'rabbitmq', 'manager':
            relevant_nodes.extend(self.relevant_nodes_dict[instance_name])
        return relevant_nodes

    def validate_certificates(self):
        self._validate_connection()
        self._validate_certificates()

    def _validate_connection(self):
        # The connection is checked first for each node
        self.raise_if_nodes_have_errors()

    def _validate_certificates(self):
        for node in self.relevant_nodes:
            node.validate_certificates()
        self.raise_if_nodes_have_errors()
        self._close_clients_connection()

    def replace_certificates(self):
        for node in self.relevant_nodes:
            node.replace_certificates()
        self.raise_if_nodes_have_errors()
        self._close_clients_connection()

    def new_cli_ca_cert(self):
        return self.config_dict['manager'].get('new_external_ca_cert_path')

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

            rabbitmq_ca_cert = self.config_dict['rabbitmq'].get('new_ca_cert')
            if rabbitmq_ca_cert:
                node_dict['new_rabbitmq_ca_cert'] = rabbitmq_ca_cert

        return node_dict

    def raise_if_nodes_have_errors(self):
        errors_list = []
        for node in self.relevant_nodes:
            errors_list.extend(node.errors_list)
        if errors_list:
            self._close_clients_connection()
            raise_errors_list(errors_list, self.logger)

    def _close_clients_connection(self):
        for node in self.relevant_nodes:
            node.connection.close()


def raise_errors_list(errors_list, logger):
    logger.info(_errors_list_str(errors_list))
    raise CloudifyCliError()


def _errors_list_str(errors_list):
    err_str = 'Errors:\n'
    err_lst = '\n'.join([' [{0}] {1}'.format(i+1, err) for i, err
                         in enumerate(errors_list)])
    return err_str + err_lst
