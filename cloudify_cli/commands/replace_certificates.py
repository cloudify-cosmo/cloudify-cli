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

from collections import OrderedDict

from .. import env
from ..cli import cfy
from ..utils import ordered_yaml_dump
from ..commands.cluster import all_in_one_manager


@cfy.group(name='replace-certificates')
@cfy.options.common_options
def replace_certificates():
    """
    Handle the certificates replacement procedure
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@replace_certificates.command(name='generate-file',
                              short_help='Generate the configuration file '
                                         'needed for certificates replacement')
@cfy.options.output_path
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get_replace_certificates_config_file(output_path,
                                         logger,
                                         client):
    output_path = (output_path if output_path
                   else 'certificates_replacement_config.yaml')
    if all_in_one_manager(client):
        pass
    else:
        manager_nodes_ips = [manager.private_ip for manager in
                             client.manager.get_managers().items]
        broker_nodes_ips = [broker.host for broker in
                            client.manager.get_brokers().items]
        db_nodes_ips = [db.host for db in client.manager.get_db_nodes().items]

        config = _get_cluster_configuration_dict(manager_nodes_ips,
                                                 db_nodes_ips,
                                                 broker_nodes_ips)
        with open(output_path, 'w') as output_file:
            # yaml.dump(config, output_file)
            ordered_yaml_dump(config, output_file)

        logger.info('The certificates replacement configuration file was '
                    'saved to {0}'.format(output_path))


def _get_cluster_configuration_dict(manager_nodes_ips,
                                    db_nodes_ips,
                                    broker_nodes_ips):
    config = OrderedDict([('instances_username', ''),
                          ('private_key_file_path', '')])
    config.update(
        {'manager': {'new_ca_cert_path': '',
                     'new_ca_key_path': '',
                     'nodes': [],
                     'external_certificates': {
                         'external_cert_path': '',
                         'external_key_path': '',
                         'external_new_ca_cert_path': ''
                     }
                     },
         'db': {'new_ca_cert_path': '',
                'nodes': []},
         'broker': {'new_ca_cert_path': '',
                    'nodes': []}
         }
    )
    _add_nodes_to_config_instance(config, 'manager', manager_nodes_ips)
    _add_nodes_to_config_instance(config, 'db', db_nodes_ips)
    _add_nodes_to_config_instance(config, 'broker', broker_nodes_ips)
    return config


def _add_nodes_to_config_instance(config, instance_name, instance_ips):
    for instance_ip in instance_ips:
        instance = {'host_ip': instance_ip,
                    'new_cert_path': '',
                    'new_key_path': ''}
        config[instance_name]['nodes'].append(instance)
