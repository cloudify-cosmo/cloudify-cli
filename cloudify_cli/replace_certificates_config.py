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

from fabric import Connection
from paramiko import AuthenticationException

from . import env
from .exceptions import CloudifyCliError


class Node(object):
    def __init__(self,
                 host_ip,
                 username,
                 key_file_path,
                 new_cert_path,
                 new_key_path,
                 logger):
        # TODO: maybe add a revert mechanism

        self.host_ip = host_ip
        self.username = username
        self.key_file_path = key_file_path
        self.connection = self._create_connection()
        self.new_cert_path = new_cert_path
        self.new_key_path = new_key_path
        self.logger = logger

        # TODO: Implement it in each node
        self.certs_mapping = None

    def _create_connection(self):
        try:
            return Connection(
                host=self.host_ip, user=self.username, port=22,
                connect_kwargs={'key_filename': self.key_file_path})

        except AuthenticationException as e:
            raise CloudifyCliError(
                "SSH: could not connect to {host} "
                "(username: {user}, key: {key}): {exc}".format(
                    host=self.host_ip, user=self.username,
                    key=self.key_file_path, exc=e))

    def run_command(self, command):
        result = self.connection.run(command, hide=True)
        self.logger.info(result.ok)

    def put_file(self, local_path, remote_path):
        result = self.connection.put(local_path, remote_path)
        self.logger.info(result.ok)

    def needs_to_replace_cert_and_key(self):
        return True if self.new_cert_path else False

    def replace_certificates(self):
        pass

    # def _prepare_new_certs_dir(self):
    #     self.run_command('mkdir {0}'.format(CERTS_TMP_DIR_PATH))


class BrokerNode(Node):
    def __init__(self, host_ip, username, key_file_path, new_cert_path,
                 new_key_path, logger):
        super(BrokerNode, self).__init__(host_ip, username, key_file_path,
                                         new_cert_path, new_key_path, logger)


class DBNode(Node):
    def __init__(self, host_ip, username, key_file_path, new_cert_path,
                 new_key_path, logger):
        super(DBNode, self).__init__(host_ip, username, key_file_path,
                                     new_cert_path, new_key_path, logger)


class ManagerNode(Node):
    def __init__(self, host_ip, username, key_file_path, new_cert_path,
                 new_key_path, logger, external_certificates_dict,
                 postgresql_client_dict, new_ldap_ca_cert):
        super(ManagerNode, self).__init__(host_ip, username, key_file_path,
                                          new_cert_path, new_key_path, logger)
        self.new_external_cert_path = external_certificates_dict.get(
            'new_external_cert_path')
        self.new_external_key_path = external_certificates_dict.get(
            'new_external_key_path')
        self.new_postgresql_client_cert_path = postgresql_client_dict.get(
            'new_postgresql_client_cert_path')
        self.new_postgresql_client_key_path = postgresql_client_dict.get(
            'new_postgresql_client_key_path')
        self.new_ldap_ca_cert = new_ldap_ca_cert


class InstanceConfig(object):
    def __init__(self, instance_config_dict, username, key_file_path, logger):
        self.new_ca_cert_path = instance_config_dict.get('new_ca_cert_path')
        self.need_certs_replacement_nodes = []
        self.all_nodes = []
        self.logger = logger
        self._create_instance_nodes(instance_config_dict,
                                    username,
                                    key_file_path)

    def _create_instance_nodes(self,
                               instance_config_dict,
                               username,
                               key_file_path):
        for node in instance_config_dict.get('nodes'):
            new_cert_path = node.get('new_cert_path')
            new_key_path = node.get('new_key_path')
            new_node = Node(node.get('host_ip'),
                            username,
                            key_file_path,
                            new_cert_path,
                            new_key_path,
                            self.logger)
            self.all_nodes.append(new_node)
            if new_cert_path and new_key_path:
                self.need_certs_replacement_nodes.append(new_node)


class ManagerInstanceConfig(InstanceConfig):
    def __init__(self, instance_config_dict, username, key_file_path, logger):
        super(ManagerInstanceConfig, self).__init__(instance_config_dict,
                                                    username,
                                                    key_file_path,
                                                    logger)
        self.new_external_ca_cert_path = instance_config_dict.get(
            'new_external_ca_cert_path')
        self.new_ldap_ca_cert_path = instance_config_dict.get(
            'new_ldap_ca_cert_path')


class DBInstanceConfig(InstanceConfig):
    def __init__(self, instance_config_dict, username, key_file_path, logger):
        super(DBInstanceConfig, self).__init__(instance_config_dict,
                                               username,
                                               key_file_path,
                                               logger)


class BrokerInstanceConfig(InstanceConfig):
    def __init__(self, instance_config_dict, username, key_file_path, logger):
        super(BrokerInstanceConfig, self).__init__(instance_config_dict,
                                                   username,
                                                   key_file_path,
                                                   logger)


class ReplaceCertificatesConfig(object):
    def __init__(self, config_dict, is_all_in_one, logger):
        self.logger = logger
        self.is_all_in_one = is_all_in_one
        self.config_dict = config_dict
        self.username = env.profile.ssh_user
        self.key_file_path = env.profile.ssh_key
        self.manager_instance = ManagerInstanceConfig(
            self.config_dict.get('manager'), self.username,
            self.key_file_path, self.logger)
        self.db_instance = DBInstanceConfig(
            self.config_dict.get('postgresql_server'), self.username,
            self.key_file_path, self.logger)
        self.broker_instance = BrokerInstanceConfig(
            self.config_dict.get('rabbitmq'), self.username,
            self.key_file_path, self.logger)

    def validate_certificates(self):
        pass

    def replace_certificates(self):
        pass
