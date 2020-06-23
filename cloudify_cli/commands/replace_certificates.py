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
from ..commands.cluster import _all_in_one_manager
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
    output_path = output_path if output_path else CERTS_CONFIG_PATH
    if _all_in_one_manager(client):
        # TODO: Take care of the AIO case
        pass
    else:
        config = _get_cluster_configuration_dict(client)
        with open(output_path, 'w') as output_file:
            ordered_yaml_dump(config, output_file)

    logger.info('The certificates replacement configuration file was '
                'saved to {0}'.format(output_path))


@replace_certificates.command(name='start',
                              short_help='Replace certificates after updating '
                                         'the configuration file')
@cfy.options.input_path()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def start_replace_certificates(input_path,
                               logger,
                               client):
    input_path = input_path if input_path else CERTS_CONFIG_PATH
    if not os.path.exists(input_path):
        raise_first_create_config_file()

    is_all_in_one = _all_in_one_manager(client)
    config_dict = get_dict_from_yaml(input_path)
    errors_list = validate_config_dict(config_dict, is_all_in_one)
    if errors_list:
        raise_errors_list(errors_list, logger)

    main_config = ReplaceCertificatesConfig(config_dict, is_all_in_one, logger)
    main_config.replace_certificates()


def _get_cluster_configuration_dict(client):
    instances_ips = _get_instances_ips(client)
    config = OrderedDict([('instances_username', ''),
                          ('private_key_file_path', '')])
    _basic_config_update(config)
    _add_nodes_to_config_instance(config, 'manager',
                                  instances_ips['manager_nodes_ips'])
    _add_nodes_to_config_instance(config, 'db',
                                  instances_ips['db_nodes_ips'])
    _add_nodes_to_config_instance(config, 'broker',
                                  instances_ips['broker_nodes_ips'])
    return config


def _add_nodes_to_config_instance(config, instance_name, instance_ips):
    for instance_ip in instance_ips:
        instance = {'host_ip': instance_ip,
                    'new_cert_path': '',
                    'new_key_path': ''}
        if instance_name == 'manager':
            external_certificates = {
                'external_certificates': {
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
        config[instance_name]['nodes'].append(instance)


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
                     'nodes': []
                     },
         'db': {'new_ca_cert_path': '',
                'nodes': []
                },
         'broker': {'new_ca_cert_path': '',
                    'nodes': []
                    }
         }
    )


def raise_first_create_config_file():
    raise CloudifyCliError('Please create the replace-certificates '
                           'configuration file first using the command'
                           ' `cfy replace-certificates generate-file`')


def validate_config_dict(config_dict, is_all_in_one):
    errors_list = []
    if is_all_in_one:
        # TODO: implement for the AIO case
        pass
    else:
        _validate_username_and_private_key(errors_list, config_dict)
        _validate_instances(errors_list, config_dict)
    return errors_list


def _validate_username_and_private_key(errors_list, config_dict):
    if ((not config_dict.get('instances_username')) or
            (not config_dict.get('private_key_file_path'))):
        errors_list.append('The instances_username or the '
                           'private_key_file_path were not specified')

    _check_path(errors_list, config_dict.get('private_key_file_path'))


def _validate_instances(errors_list, config_dict):
    manager_section = config_dict.get('manager')
    external_certificates = manager_section['external_certificates']
    _validate_manager_ca_cert_and_key(errors_list, manager_section)
    _validate_external_certs(errors_list, external_certificates)
    for instance in 'manager', 'db', 'broker':
        _validate_nodes(errors_list, config_dict[instance]['nodes'])
    # TODO: Validate that if a new CA was given, also new certs are needed.
    #  Maybe besides manager case where we're supposed to generate them?


def _validate_external_certs(errors_list, external_certs):
    if (external_certs.get('new_external_ca_key_path') and
            (not external_certs.get('new_external_ca_cert_path'))):
        errors_list.append('Please provide the new_external_ca_cert_path '
                           'in addition to the new_external_ca_key_path')

    if (bool(external_certs.get('new_external_cert_path')) !=
            bool(external_certs.get('new_external_key_path'))):
        errors_list.append('Please specify both the new_cert_path '
                           'and new_key_path or none of them for external '
                           'certificates')

    for path in external_certs.values():
        _check_path(errors_list, path)


def _validate_manager_ca_cert_and_key(errors_list, manager_section):
    new_ca_cert_path = manager_section.get('new_ca_cert_path')
    new_ca_key_path = manager_section.get('new_ca_key_path')
    _check_path(errors_list, new_ca_cert_path)
    _check_path(errors_list, new_ca_key_path)
    if new_ca_key_path and (not new_ca_cert_path):
        errors_list.append('Please provide the new_ca_cert_path in '
                           'addition to the new_ca_key_path')


def _validate_nodes(errors_list, nodes):
    for node in nodes:
        new_cert_path = node.get('new_cert_path')
        new_key_path = node.get('new_key_path')
        if bool(new_cert_path) != bool(new_key_path):
            errors_list.append('Please specify both the new_cert_path '
                               'and new_key_path or none of them for node '
                               'with IP {0}'.format(node['host_ip']))
        _check_path(errors_list, new_cert_path)
        _check_path(errors_list, new_key_path)


def _check_path(errors_list, path):
    if path and (not os.path.exists(path)):
        errors_list.append('The path {0} does not exist'.format(path))


def raise_errors_list(errors_list, logger):
    logger.info('Errors:')
    for error in errors_list:
        # TODO: check the printing
        logger.info(error)
    raise CloudifyCliError('\nPlease go over the errors above')
