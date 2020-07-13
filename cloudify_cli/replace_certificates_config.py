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

import yaml

from . import env, constants
from .exceptions import CloudifyCliError

try:
    from fabric import Connection
    from paramiko import AuthenticationException
except ImportError:
    Connection = None

CONFIG_FILE_PATH = '/{0}replace_certificates_config.yaml'
LOCAL_CONFIG_FILE_PATH = '/tmp' + CONFIG_FILE_PATH
REMOTE_CONFIG_FILE_PATH = constants.NEW_CERTS_TMP_DIR_PATH + \
                          CONFIG_FILE_PATH.format('')


class Node(object):
    def __init__(self,
                 host_ip,
                 username,
                 key_file_path,
                 new_cert_path,
                 new_key_path,
                 new_ca_path,
                 logger):
        self.host_ip = host_ip
        self.username = username
        self.key_file_path = key_file_path
        self.connection = self._create_connection()
        self.new_cert_path = new_cert_path
        self.new_key_path = new_key_path
        self.new_ca_path = new_ca_path
        self.certs_mapping = self._create_paths_mapping()
        self.certs_dict = {}
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

    @abc.abstractmethod
    def _create_paths_mapping(self):
        pass

    def run_command(self, command):
        result = self.connection.run(command, hide=True)
        self._check_if_command_failed(command, result)

    def put_file(self, local_path, remote_path):
        command = '`copy local {0} to remote {1}`'.format(
            local_path, remote_path)
        result = self.connection.put(local_path, remote_path)
        self._check_if_command_failed(command, result)

    def _check_if_command_failed(self, command, result):
        if not result.ok:
            self.errors_list.append('The command `{0}` on host {1} '
                                    'failed'.format(command, self.host_ip))

    def replace_certificates(self):
        self.run_command('cfy_manager replace-certificates')

    def validate_certificates(self):
        self.run_command('cfy_manager replace-certificates -i {0}'
                         ' --validate-only'.format(REMOTE_CONFIG_FILE_PATH))

    def needs_to_replace_certificates(self):
        return any([val[0] for val in self.certs_mapping.values()])

    def pass_certificates(self):
        self._prepare_new_certs_dir()
        for cert, locations in self.certs_mapping.items():
            local_cert, remote_cert = locations
            if local_cert:
                self.certs_dict[cert] = remote_cert
                self.put_file(local_cert, remote_cert)

        self._pass_config_file()

    def _pass_config_file(self):
        local_path = LOCAL_CONFIG_FILE_PATH.format(self.host_ip+'_')
        with open(local_path, 'w') as config_file:
            yaml.dump(self.certs_dict, config_file)

        self.put_file(local_path, REMOTE_CONFIG_FILE_PATH)
        os.remove(local_path)

    def _prepare_new_certs_dir(self):
        self.run_command('mkdir {0}'.format(constants.NEW_CERTS_TMP_DIR_PATH))


class BrokerNode(Node):
    def __init__(self, host_ip, username, key_file_path, new_cert_path,
                 new_key_path, new_ca_path, logger):
        super(BrokerNode, self).__init__(host_ip, username, key_file_path,
                                         new_cert_path, new_key_path,
                                         new_ca_path, logger)

    def _create_paths_mapping(self):
        return {
            'new_rabbitmq_cert_path':
                (self.new_cert_path, constants.NEW_BROKER_CERT_FILE_PATH),
            'new_rabbitmq_key_path':
                (self.new_key_path, constants.NEW_BROKER_KEY_FILE_PATH),
            'new_rabbitmq_ca_path':
                (self.new_ca_path, constants.NEW_BROKER_CA_CERT_FILE_PATH)
        }


class DBNode(Node):
    def __init__(self, host_ip, username, key_file_path, new_cert_path,
                 new_key_path, new_ca_path, logger):
        super(DBNode, self).__init__(host_ip, username, key_file_path,
                                     new_cert_path, new_key_path,
                                     new_ca_path, logger)

    def _create_paths_mapping(self):
        return {
            'new_postgresql_cert_path':
                (self.new_cert_path, constants.NEW_POSTGRESQL_CERT_FILE_PATH),
            'new_postgresql_key_path':
                (self.new_key_path, constants.NEW_POSTGRESQL_KEY_FILE_PATH),
            'new_postgresql_ca_path':
                (self.new_ca_path, constants.NEW_POSTGRESQL_CA_CERT_FILE_PATH)
        }


class ManagerNode(Node):
    def __init__(self,
                 host_ip, username, key_file_path,
                 new_cert_path, new_key_path, new_ca_path,
                 external_certificates_dict, new_external_ca_cert,
                 postgresql_client_dict, postgresql_config_dict,
                 new_ldap_ca_cert, logger):
        super(ManagerNode, self).__init__(host_ip, username, key_file_path,
                                          new_cert_path, new_key_path,
                                          new_ca_path, logger)
        self.new_external_cert_path = external_certificates_dict.get(
            'new_external_cert_path')
        self.new_external_key_path = external_certificates_dict.get(
            'new_external_key_path')
        self.new_external_ca_cert = new_external_ca_cert
        self.new_postgresql_client_cert_path = postgresql_client_dict.get(
            'new_postgresql_client_cert_path')
        self.new_postgresql_client_key_path = postgresql_client_dict.get(
            'new_postgresql_client_key_path')
        self.new_postgresql_ca_cert_path = postgresql_config_dict.get(
            'new_ca_cert_path')
        self.new_ldap_ca_cert = new_ldap_ca_cert

    def _create_paths_mapping(self):
        return {
            'new_internal_cert_path':
                (self.new_cert_path, constants.NEW_INTERNAL_CERT_FILE_PATH),
            'new_internal_key_path':
                (self.new_key_path, constants.NEW_INTERNAL_KEY_FILE_PATH),
            'new_ca_path':
                (self.new_ca_path, constants.NEW_INTERNAL_CA_CERT_FILE_PATH),
            'new_external_cert_path': (self.new_external_cert_path,
                                       constants.NEW_EXTERNAL_CERT_FILE_PATH),
            'new_external_key_path': (self.new_external_key_path,
                                      constants.NEW_EXTERNAL_KEY_FILE_PATH),
            'new_external_ca_path': (self.new_external_ca_cert,
                                     constants.NEW_EXTERNAL_CA_CERT_FILE_PATH),
            'new_postgresql_client_cert_path': (
                self.new_postgresql_client_cert_path,
                constants.NEW_POSTGRESQL_CLIENT_CERT_FILE_PATH),
            'new_postgresql_client_key_path':
                (self.new_postgresql_client_key_path,
                 constants.NEW_POSTGRESQL_CLIENT_KEY_FILE_PATH),
            'new_postgresql_ca_path':
                (self.new_postgresql_ca_cert_path,
                 constants.NEW_POSTGRESQL_CA_CERT_FILE_PATH),
            'new_ldap_ca_path': (self.new_ldap_ca_cert,
                                 constants.NEW_LDAP_CA_CERT_PATH)
        }


class InstanceConfig(object):
    def __init__(self, instance_config_dict, username, key_file_path,
                 node_type, logger):
        self.node_type = node_type
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
        for node in instance_config_dict.get('cluster_members'):
            new_cert_path = node.get('new_cert_path')
            new_key_path = node.get('new_key_path')
            new_ca_path = instance_config_dict.get('new_ca_cert_path')
            new_node = self.node_type(node.get('host_ip'),
                                      username,
                                      key_file_path,
                                      new_cert_path,
                                      new_key_path,
                                      new_ca_path,
                                      self.logger)
            self.all_nodes.append(new_node)
            if new_node.needs_to_replace_certificates():
                self.need_certs_replacement_nodes.append(new_node)


class ManagerInstanceConfig(InstanceConfig):
    def __init__(self, instance_config_dict, username, key_file_path,
                 new_postgresql_ca_path, logger):
        super(ManagerInstanceConfig, self).__init__(instance_config_dict,
                                                    username,
                                                    key_file_path,
                                                    ManagerNode,
                                                    logger)
        self.new_postgresql_ca_path = new_postgresql_ca_path

    def _create_instance_nodes(self,
                               instance_config_dict,
                               username,
                               key_file_path):
        for node in instance_config_dict.get('cluster_members'):
            new_cert_path = node.get('new_cert_path')
            new_key_path = node.get('new_key_path')
            new_ca_path = instance_config_dict.get('new_ca_cert_path')
            new_node = ManagerNode(
                node.get('host_ip'), username, key_file_path,
                new_cert_path, new_key_path, new_ca_path,
                node.get('new_node_external_certificates'),
                node.get('new_external_ca_cert_path'),
                node.get('postgresql_client'),
                self.new_postgresql_ca_path,
                node.get('new_ldap_ca_cert_path'),
                self.logger)
            self.all_nodes.append(new_node)
            if new_cert_path or new_ca_path:
                self.need_certs_replacement_nodes.append(new_node)


class DBInstanceConfig(InstanceConfig):
    def __init__(self, instance_config_dict, username, key_file_path, logger):
        super(DBInstanceConfig, self).__init__(instance_config_dict,
                                               username,
                                               key_file_path,
                                               DBNode,
                                               logger)


class BrokerInstanceConfig(InstanceConfig):
    def __init__(self, instance_config_dict, username, key_file_path, logger):
        super(BrokerInstanceConfig, self).__init__(instance_config_dict,
                                                   username,
                                                   key_file_path,
                                                   BrokerNode,
                                                   logger)


class ReplaceCertificatesConfig(object):
    def __init__(self, config_dict, is_all_in_one, logger):
        if Connection is None:
            raise CloudifyCliError("SSH not available - fabric not installed")

        self.logger = logger
        self.is_all_in_one = is_all_in_one
        self.config_dict = config_dict
        self.username = env.profile.ssh_user
        self.key_file_path = env.profile.ssh_key
        self.manager_instance = ManagerInstanceConfig(
            self.config_dict.get('manager'), self.username,
            self.key_file_path,  self.config_dict.get('postgresql_server'),
            self.logger)
        self.db_instance = DBInstanceConfig(
            self.config_dict.get('postgresql_server'), self.username,
            self.key_file_path, self.logger)
        self.broker_instance = BrokerInstanceConfig(
            self.config_dict.get('rabbitmq'), self.username,
            self.key_file_path, self.logger)
        self.needs_to_replace_certificates = len(self.relevant_nodes) > 0

    @property
    def relevant_nodes(self):
        relevant_nodes = []
        for instance in [self.db_instance, self.broker_instance,
                         self.manager_instance]:
            relevant_nodes.extend(instance.need_certs_replacement_nodes)
        return relevant_nodes

    def validate_certificates(self):
        if not self._validate_connection():
            return False
        if not self._pass_certs_to_nodes():
            return False
        if not self._validate_certificates():
            return False

        return True

    def _validate_connection(self):
        return self._nodes_have_errors()

    def _pass_certs_to_nodes(self):
        for node in self.relevant_nodes:
            node.pass_certificates()
        return self._nodes_have_errors()

    def _validate_certificates(self):
        for node in self.relevant_nodes:
            node.validate_certificates()
        return self._nodes_have_errors()

    def replace_certificates(self):
        for node in self.relevant_nodes:
            node.replace_certificates()
        return self._nodes_have_errors()

    def _nodes_have_errors(self):
        have_errors = False
        for node in self.relevant_nodes:
            if node.errors_list:
                have_errors = True
                for err_msg in node.errors_list:
                    self.logger.error(err_msg)
        return have_errors
