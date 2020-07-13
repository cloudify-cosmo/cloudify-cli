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
from collections import OrderedDict

from .. import env
from ..cli import cfy
from ..exceptions import CloudifyCliError
from ..utils import ordered_yaml_dump, get_dict_from_yaml
from ..replace_certificates_config import ReplaceCertificatesConfig

CERTS_CONFIG_PATH = 'certificates_replacement_config.yaml'


@cfy.group(name='replace-certificates')
@cfy.options.common_options
def replace_certificates():
    """
    Handle the certificates replacement procedure
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@replace_certificates.command(name='generate-config',
                              short_help='Generate the configuration file '
                                         'needed for certificates replacement')
@cfy.options.output_path
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get_replace_certificates_config_file(output_path,
                                         logger,
                                         client):
    # TODO: Take care of the AIO case
    output_path = output_path if output_path else CERTS_CONFIG_PATH
    config = _get_cluster_configuration_dict(client)
    with open(output_path, 'w') as output_file:
        ordered_yaml_dump(config, output_file)

    logger.info('The certificates replacement configuration file was '
                'saved to {0}'.format(output_path))


@replace_certificates.command(name='start',
                              short_help='Replace certificates after updating '
                                         'the configuration file')
@cfy.options.input_path(help='The certificates replacement configuration file')
@cfy.options.force('Use the force flag in case you want to change only a '
                   'CA and not the certificates signed by it')
@cfy.assert_manager_active()
@cfy.pass_logger
def start_replace_certificates(input_path,
                               force,
                               logger):
    # TODO: implement for the AIO case
    _validate_username_and_private_key()
    config_dict = get_dict_from_yaml(_get_input_path(input_path))
    errors_list = validate_config_dict(config_dict, force, logger)
    if errors_list:
        raise_errors_list(errors_list, logger)

    main_config = ReplaceCertificatesConfig(config_dict, False, logger)
    are_certs_valid = main_config.validate_certificates()
    if are_certs_valid:
        main_config.replace_certificates()


def _get_input_path(input_path):
    input_path = input_path if input_path else CERTS_CONFIG_PATH
    if not os.path.exists(input_path):
        raise CloudifyCliError('Please create the replace-certificates '
                               'configuration file first using the command'
                               ' `cfy replace-certificates generate-file`')
    return input_path


def _get_cluster_configuration_dict(client):
    instances_ips = _get_instances_ips(client)
    config = OrderedDict()
    _basic_config_update(config)
    _add_nodes_to_config_instance(config, 'manager',
                                  instances_ips['manager_nodes_ips'])
    _add_nodes_to_config_instance(config, 'postgresql_server',
                                  instances_ips['db_nodes_ips'])
    _add_nodes_to_config_instance(config, 'rabbitmq',
                                  instances_ips['broker_nodes_ips'])
    return config


def _add_nodes_to_config_instance(config, instance_name, instance_ips):
    for node_ip in instance_ips:
        instance = {'host_ip': node_ip,
                    'new_cert_path': '',
                    'new_key_path': ''}
        config[instance_name]['cluster_members'].append(instance)
        if instance_name == 'manager':
            external_certificates = {
                'new_node_external_certificates': {
                    'new_external_cert_path': '',
                    'new_external_key_path': ''
                }
            }
            postgresql_client = {
                'postgresql_client': {
                    'new_postgresql_client_cert_path': '',
                    'new_postgresql_client_key_path': '',
                }
            }
            instance.update(external_certificates)
            instance.update(postgresql_client)


def _get_instances_ips(client):
    return {'manager_nodes_ips': [manager.private_ip for manager in
                                  client.manager.get_managers().items],
            'broker_nodes_ips': [broker.host for broker in
                                 client.manager.get_brokers().items],
            'db_nodes_ips': [db.host for db in
                             client.manager.get_db_nodes().items]
            }


def _basic_config_update(config):
    config.update(
        {'manager': {'new_ca_cert_path': '',
                     'new_external_ca_cert_path': '',
                     'new_ldap_ca_cert_path': '',
                     'cluster_members': []
                     },
         'postgresql_server': {'new_ca_cert_path': '',
                               'cluster_members': []
                               },
         'rabbitmq': {'new_ca_cert_path': '',
                      'cluster_members': []
                      }
         }
    )


def validate_config_dict(config_dict, force, logger):
    errors_list = []
    _validate_instances(errors_list, config_dict, force, logger)
    _validate_external_ca_cert(errors_list, config_dict, force, logger)
    _validate_postgresql_client_ca(errors_list, config_dict, force, logger)
    _check_path(errors_list, config_dict['manager']['new_ldap_ca_cert_path'])
    return errors_list


def _validate_username_and_private_key():
    # TODO: what if the client is also the manager in the AIO case?
    if (not env.profile.ssh_user) or (not env.profile.ssh_key):
        raise CloudifyCliError('Please configure the profile ssh-key and '
                               'ssh-user using the `cfy profiles set` command')


def _validate_instances(errors_list, config_dict, force, logger):
    for instance in 'manager', 'postgresql_server', 'rabbitmq':
        _validate_cert_and_key(errors_list,
                               config_dict[instance]['cluster_members'],
                               instance == 'manager')
        _validate_new_ca_cert(errors_list, config_dict, instance, force,
                              logger)


def _validate_new_ca_cert(errors_list, config_dict, instance, force, logger):
    _validate_ca_cert(errors_list, config_dict[instance], instance,
                      'new_ca_cert_path',
                      config_dict[instance]['cluster_members'],
                      'new_cert_path', force, logger)


def _validate_external_ca_cert(errors_list, config_dict, force, logger):
    external_certs_list = [member['new_node_external_certificates'] for
                           member in config_dict['manager']['cluster_members']]

    _validate_ca_cert(errors_list, config_dict['manager'], 'manager',
                      'new_external_ca_cert_path', external_certs_list,
                      'new_external_cert_path', force, logger)


def _validate_postgresql_client_ca(errors_list, config_dict, force, logger):
    postgresql_certs_list = [member['postgresql_client'] for member in
                             config_dict['manager']['cluster_members']]

    _validate_ca_cert(errors_list, config_dict['postgresql_server'],
                      'postgresql_server', 'new_ca_cert_path',
                      postgresql_certs_list, 'new_postgresql_client_cert_path',
                      force, logger)


def _validate_ca_cert(errors_list, instance, instance_name, new_ca_cert_name,
                      cluster_members, cert_name, force, logger):
    err_msg = '{0} was specified for instance {1}, but {2} was not specified' \
              ' for all cluster members.'.format(new_ca_cert_name,
                                                 instance_name,
                                                 cert_name)

    new_ca_cert_path = instance.get(new_ca_cert_name)
    if _check_path(errors_list, new_ca_cert_path):
        if not all(member.get(cert_name) for member in cluster_members):
            if force:
                logger.info(err_msg)
            else:
                errors_list.append(err_msg +
                                   ' Please use `--force` if you still wish '
                                   'to replace the certificates')


def _validate_cert_and_key(errors_list, nodes, is_manager):
    for node in nodes:
        _validate_node_certs(errors_list, node, 'new_cert_path',
                             'new_key_path')
        if is_manager:
            certs_dict = {'host_ip': node['host_ip']}
            certs_dict.update(node['new_node_external_certificates'])
            certs_dict.update(node['postgresql_client'])
            _validate_node_certs(errors_list,
                                 certs_dict,
                                 'new_external_cert_path',
                                 'new_external_key_path')
            _validate_node_certs(errors_list,
                                 certs_dict,
                                 'new_postgresql_client_cert_path',
                                 'new_postgresql_client_key_path')


def _validate_node_certs(errors_list, certs_dict, new_cert_name, new_key_name):
    new_cert_path = certs_dict.get(new_cert_name)
    new_key_path = certs_dict.get(new_key_name)
    if bool(new_key_path) != bool(new_cert_path):
        errors_list.append('Either both cert_path and key_path must be '
                           'provided, or neither for host '
                           '{0}'.format(certs_dict['host_ip']))
    _check_path(errors_list, new_cert_path)
    _check_path(errors_list, new_key_path)


def _check_path(errors_list, path):
    if path:
        if os.path.exists(path):
            return True
        errors_list.append('The path {0} does not exist'.format(path))
    return False


def raise_errors_list(errors_list, logger):
    logger.info('Errors:')
    for error in errors_list:
        # TODO: check the printing
        logger.info(error)
    raise CloudifyCliError('\nPlease go over the errors above')
