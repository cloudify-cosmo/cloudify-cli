class Node(object):
    def __init__(self, host_ip, username, key_file_path):
        # TODO: verify cert and key match
        pass


class InstanceConfig(object):
    def __init__(self, instance_config_dict, username, key_file_path):
        self.new_ca_cert_path = instance_config_dict.get('new_ca_cert_path')
        self.relevant_nodes = []
        self.all_nodes = []
        self._create_instance_nodes(instance_config_dict, username,
                                    key_file_path)

    def _create_instance_nodes(self, instance_config_dict, username,
                               key_file_path):
        for node in instance_config_dict.get('nodes'):
            new_cert_path = node.get('new_cert_path')
            new_key_path = node.get('new_key_path')
            new_node = Node(node.get('host_ip'), username, key_file_path)
            self.all_nodes.append(new_node)
            if new_cert_path and new_key_path:
                self.relevant_nodes.append(new_node)


class ManagerInstanceConfig(InstanceConfig):
    def __init__(self, instance_config_dict, username, key_file_path):
        super(ManagerInstanceConfig, self).__init__(instance_config_dict,
                                                    username, key_file_path)
        self.external_certs = instance_config_dict.get('external_certificates')
        self.new_ca_key_path = instance_config_dict.get('new_ca_key_path')


class DBInstanceConfig(InstanceConfig):
    def __init__(self, instance_config_dict, username, key_file_path):
        super(DBInstanceConfig, self).__init__(instance_config_dict,
                                               username, key_file_path)


class BrokerInstanceConfig(InstanceConfig):
    def __init__(self, instance_config_dict, username, key_file_path):
        super(BrokerInstanceConfig, self).__init__(instance_config_dict,
                                                   username, key_file_path)


class ReplaceCertificatesConfig(object):
    def __init__(self, config_dict, is_all_in_one, logger):
        self.logger = logger
        self.is_all_in_one = is_all_in_one
        self.config_dict = config_dict
