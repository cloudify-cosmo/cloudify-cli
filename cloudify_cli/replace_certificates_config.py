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

import os
import abc
import time
import select
from contextlib import contextmanager

import yaml

from . import env
from .constants import CERTS_MAPPING, NEW_CERTS_TMP_DIR_PATH
from .exceptions import CloudifyCliError

try:
    from paramiko import SSHClient, AutoAddPolicy
except ImportError:
    SSHClient = None

CONFIG_FILE_PATH = '{0}replace_certificates_config.yaml'
LOCAL_CONFIG_FILE_PATH = '/tmp/' + CONFIG_FILE_PATH
REMOTE_CONFIG_FILE_PATH = NEW_CERTS_TMP_DIR_PATH + CONFIG_FILE_PATH.format('')


def retry_with_sleep(func, *func_args, **kwargs):
    retry_count = kwargs.get('retry_count', 15)
    delay = kwargs.get('delay', 2)
    for i in range(retry_count):
        try:
            return func(*func_args)
        except Exception as e:
            if i < retry_count - 1:
                time.sleep(delay)
                continue
            else:
                raise e


class Node(object):
    def __init__(self,
                 host_ip,
                 username,
                 key_file_path,
                 new_cert_path,
                 new_key_path,
                 new_ca_cert_path,
                 logger):
        self.host_ip = host_ip
        self.username = username
        self.key_file_path = key_file_path
        self.client = self._create_ssh_client()
        self.new_cert_path = new_cert_path
        self.new_key_path = new_key_path
        self.new_ca_cert_path = new_ca_cert_path
        self.certs_mapping = self._create_paths_mapping()
        self.certs_dict = {}
        self.errors_list = []
        self.logger = logger

    @staticmethod
    def _create_ssh_client_func(hostname, username, key_file):
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        client.connect(hostname=hostname, username=username,
                       key_filename=key_file)
        return client

    def _create_ssh_client(self):
        return retry_with_sleep(self._create_ssh_client_func,
                                self.host_ip, self.username,
                                self.key_file_path)

    def _blocking_exec_command(self, command):
        stdin, stdout, stderr = self.client.exec_command(command)
        channel = stdout.channel
        output = ''

        stdin.close()
        channel.shutdown_write()

        first_msg = stdout.channel.recv(len(stdout.channel.in_buffer))
        if first_msg:
            self.logger.info(first_msg)
        while not channel.closed or channel.recv_ready() or \
                channel.recv_stderr_ready():

            got_chunk = False
            readq, _, _ = select.select([stdout.channel], [], [], 180)
            for c in readq:
                if c.recv_ready():
                    output = stdout.channel.recv(len(c.in_buffer))
                    self.logger.info(output)
                    got_chunk = True
                if c.recv_stderr_ready():
                    output = stderr.channel.recv_stderr(
                        len(c.in_stderr_buffer))
                    got_chunk = True

            if not got_chunk \
                    and stdout.channel.exit_status_ready() \
                    and not stderr.channel.recv_stderr_ready() \
                    and not stdout.channel.recv_ready():
                stdout.channel.shutdown_read()
                stdout.channel.close()
                break

        stdout.close()
        stderr.close()

        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            raise CloudifyCliError(output)

        return output

    @abc.abstractmethod
    def _create_paths_mapping(self):
        pass

    def run_command(self, command):
        try:
            self.logger.debug('Running `{0}` on '
                              '{1}'.format(command, self.host_ip))
            return self._blocking_exec_command(command)
        except CloudifyCliError as err:
            self._command_failed(command, err.message)

    @contextmanager
    def sftp_connection(self):
        sftp = None
        try:
            sftp = self.client.open_sftp()
            yield sftp
        finally:
            if sftp:
                sftp.close()

    def put_file(self, local_path, remote_path):
        self.logger.debug('Copying {0} to {1} on host {2}'.format(
            local_path, remote_path, self.host_ip))
        with self.sftp_connection() as sftp:
            sftp.put(local_path, remote_path)

    def _command_failed(self, command, err_msg):
        self.errors_list.append('The command `{0}` on host {1} '
                                'failed with error: '
                                '{2}'.format(command, self.host_ip, err_msg))

    def replace_certificates(self):
        self.logger.info(('Replacing certificates on host '
                          '{0}'.format(self.host_ip)))
        self.run_command('cfy_manager replace-certificates -i '
                         '{0}'.format(REMOTE_CONFIG_FILE_PATH))

    def validate_certificates(self):
        self.logger.info(('Validating certificates on host '
                          '{0}'.format(self.host_ip)))
        self._pass_certificates()
        self.run_command('cfy_manager replace-certificates -i {0}'
                         ' --only-validate'.format(REMOTE_CONFIG_FILE_PATH))

    def needs_to_replace_certificates(self):
        return any(self.certs_mapping.values())

    def _pass_certificates(self):
        self._prepare_new_certs_dir()
        for cert_name, new_cert_path in self.certs_mapping.items():
            if new_cert_path:
                remote_cert_path = CERTS_MAPPING[cert_name]
                self.certs_dict[cert_name] = remote_cert_path
                self.put_file(new_cert_path, remote_cert_path)

        self._pass_config_file()

    def _pass_config_file(self):
        local_path = LOCAL_CONFIG_FILE_PATH.format(self.host_ip + '_')
        with open(local_path, 'w') as config_file:
            yaml.dump(self.certs_dict, config_file)

        self.put_file(local_path, REMOTE_CONFIG_FILE_PATH)
        os.remove(local_path)

    def _prepare_new_certs_dir(self):
        self.run_command('rm -r {0}; mkdir {0}'.format(
            NEW_CERTS_TMP_DIR_PATH))


class BrokerNode(Node):
    def __init__(self, host_ip, username, key_file_path, new_cert_path,
                 new_key_path, new_ca_cert_path, logger):
        super(BrokerNode, self).__init__(host_ip, username, key_file_path,
                                         new_cert_path, new_key_path,
                                         new_ca_cert_path, logger)

    def _create_paths_mapping(self):
        return {
            'new_rabbitmq_cert_path': self.new_cert_path,
            'new_rabbitmq_key_path': self.new_key_path,
            'new_rabbitmq_ca_cert_path': self.new_ca_cert_path
        }


class DBNode(Node):
    def __init__(self, host_ip, username, key_file_path, new_cert_path,
                 new_key_path, new_ca_cert_path, logger):
        super(DBNode, self).__init__(host_ip, username, key_file_path,
                                     new_cert_path, new_key_path,
                                     new_ca_cert_path, logger)

    def _create_paths_mapping(self):
        return {
            'new_postgresql_cert_path': self.new_cert_path,
            'new_postgresql_key_path': self.new_key_path,
            'new_postgresql_ca_cert_path': self.new_ca_cert_path
        }


class ManagerNode(Node):
    def __init__(self,
                 host_ip,
                 username,
                 key_file_path,
                 new_internal_cert_path,
                 new_internal_key_path,
                 new_external_cert_path,
                 new_external_key_path,
                 new_postgresql_client_cert_path,
                 new_postgresql_client_key_path,
                 new_ca_cert_path,
                 new_external_ca_cert_path,
                 new_postgresql_ca_cert_path,
                 new_ldap_ca_cert_path,
                 logger):
        self.new_external_cert_path = new_external_cert_path
        self.new_external_key_path = new_external_key_path
        self.new_external_ca_cert = new_external_ca_cert_path
        self.new_postgresql_client_cert_path = new_postgresql_client_cert_path
        self.new_postgresql_client_key_path = new_postgresql_client_key_path
        self.new_postgresql_ca_cert_path = new_postgresql_ca_cert_path
        self.new_ldap_ca_cert_path = new_ldap_ca_cert_path

        super(ManagerNode, self).__init__(host_ip, username, key_file_path,
                                          new_internal_cert_path,
                                          new_internal_key_path,
                                          new_ca_cert_path, logger)

    def _create_paths_mapping(self):
        return {
            'new_internal_cert_path': self.new_cert_path,
            'new_internal_key_path': self.new_key_path,
            'new_ca_cert_path': self.new_ca_cert_path,
            'new_external_cert_path': self.new_external_cert_path,
            'new_external_key_path': self.new_external_key_path,
            'new_external_ca_cert_path': self.new_external_ca_cert,
            'new_postgresql_client_cert_path':
                self.new_postgresql_client_cert_path,
            'new_postgresql_client_key_path':
                self.new_postgresql_client_key_path,
            'new_postgresql_ca_cert_path': self.new_postgresql_ca_cert_path,
            'new_ldap_ca_cert_path': self.new_ldap_ca_cert_path
        }


class ReplaceCertificatesConfig(object):
    def __init__(self, config_dict, is_all_in_one, logger):
        if SSHClient is None:
            raise CloudifyCliError("SSH not available - fabric not installed")

        self.logger = logger
        self.is_all_in_one = is_all_in_one
        self.config_dict = config_dict
        self.username = env.profile.ssh_user
        self.key_file_path = env.profile.ssh_key
        self.all_nodes = []
        self.relevant_nodes_dict = {'manager': [],
                                    'postgresql_server': [],
                                    'rabbitmq': []}
        self._create_manager_nodes()
        self._create_nodes(DBNode, 'postgresql_server')
        self._create_nodes(BrokerNode, 'rabbitmq')
        self.needs_to_replace_certificates = len(self.relevant_nodes) > 0

    @property
    def relevant_nodes(self):
        relevant_nodes = []
        for instance_name in 'postgresql_server', 'rabbitmq', 'manager':
            relevant_nodes.extend(self.relevant_nodes_dict[instance_name])
        return relevant_nodes

    def validate_certificates(self):
        if not self._validate_connection():
            self._close_clients_connection()
            return False
        if not self._validate_certificates():
            self._close_clients_connection()
            return False

        self._close_clients_connection()
        return True

    def _validate_connection(self):
        return not self._nodes_have_errors()

    def _validate_certificates(self):
        for node in self.relevant_nodes:
            node.validate_certificates()
        return not self._nodes_have_errors()

    def replace_certificates(self):
        for node in self.relevant_nodes:
            node.replace_certificates()
        return not self._nodes_have_errors()

    def _nodes_have_errors(self):
        have_errors = False
        for node in self.relevant_nodes:
            if node.errors_list:
                have_errors = True
                for err_msg in node.errors_list:
                    self.logger.error(err_msg)
        return have_errors

    def new_cli_ca_cert(self):
        return self.config_dict['manager'].get('new_external_ca_cert_path')

    def _create_manager_nodes(self):
        for node in self.config_dict['manager']['cluster_members']:
            new_node = ManagerNode(
                node.get('host_ip'),
                self.username,
                self.key_file_path,
                node.get('new_internal_cert_path'),
                node.get('new_internal_key_path'),
                node.get('new_external_cert_path'),
                node.get('new_external_key_path'),
                node.get('new_postgresql_client_cert_path'),
                node.get('new_postgresql_client_key_path'),
                self.config_dict['manager'].get('new_ca_cert_path'),
                self.config_dict['manager'].get('new_external_ca_cert_path'),
                self.config_dict['postgresql_server'].get('new_ca_cert_path'),
                self.config_dict['manager'].get('new_ldap_ca_cert_path'),
                self.logger
            )
            if new_node.needs_to_replace_certificates():
                self.relevant_nodes_dict['manager'].append(new_node)

    def _create_nodes(self, instance_type, instance_name):
        for node in self.config_dict[instance_name]['cluster_members']:
            new_node = instance_type(
                node.get('host_ip'),
                self.username,
                self.key_file_path,
                node.get('new_cert_path'),
                node.get('new_key_path'),
                self.config_dict[instance_name].get('new_ca_cert_path'),
                self.logger
            )
            if new_node.needs_to_replace_certificates():
                self.relevant_nodes_dict[instance_name].append(new_node)

    def _close_clients_connection(self):
        for node in self.all_nodes:
            node.client.close()
