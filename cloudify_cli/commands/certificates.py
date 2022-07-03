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

import yaml


from cloudify_cli import env
from cloudify_cli.cli import cfy
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.replace_certificates_config import ReplaceCertificatesConfig
from cloudify_cli.utils import get_dict_from_yaml

from cloudify_cli.commands.cluster import _all_in_one_manager

CERTS_CONFIG_PATH = 'certificates_replacement_config.yaml'


@cfy.group(name='certificates')
@cfy.options.common_options
def certificates():
    """
    Handle certificates related procedures
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@certificates.command(name='generate-replace-config',
                      short_help='Generate the configuration file needed for '
                                 'certificates replacement')
@cfy.options.output_path
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def get_replace_certificates_config_file(output_path,
                                         logger,
                                         client):
    # output_path is not a default param because of `cfy.options.output_path`
    output_path = output_path if output_path else CERTS_CONFIG_PATH
    config = _get_configuration_dict(client)
    with open(output_path, 'w') as output_file:
        yaml.dump(config, output_file, default_flow_style=False)

    logger.info('The certificates replacement configuration file was '
                'saved to %s', output_path)


@certificates.command(name='replace',
                      short_help='Replace certificates after updating the '
                                 'configuration file')
@cfy.options.input_path(help='The certificates replacement configuration file')
@cfy.options.verbose()
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def start_replace_certificates(input_path,
                               logger,
                               client):
    _validate_admin_user_role(client)
    _validate_username_and_private_key()
    is_all_in_one = _all_in_one_manager(client)
    config_dict = get_dict_from_yaml(_get_input_path(input_path))
    logger.info('Validating replace-certificates config file...')
    validate_config_dict(config_dict, is_all_in_one, logger)

    main_config = ReplaceCertificatesConfig(config_dict, is_all_in_one,
                                            client, logger)
    main_config.validate_certificates()
    main_config.replace_certificates()


def _validate_admin_user_role(client):
    current_username = env.get_username()
    user = client.users.get(current_username)
    if not user.role == 'sys_admin':
        raise CloudifyCliError('`cfy replace-certificates start` is '
                               'restricted to users with sys-admin role.')


def _get_input_path(input_path):
    input_path = input_path if input_path else CERTS_CONFIG_PATH
    if not os.path.exists(input_path):
        raise CloudifyCliError('Please create the replace-certificates '
                               'configuration file first')
    return input_path


def _get_configuration_dict(client):
    if _all_in_one_manager(client):
        return {
            'manager': {
                'new_internal_cert': '',
                'new_internal_key': '',
                'new_external_cert': '',
                'new_external_key': '',
                'new_postgresql_client_cert': '',
                'new_postgresql_client_key': '',
                'new_prometheus_cert': '',     # Relevant only if
                'new_prometheus_key': '',      # monitoring_service
                'new_prometheus_ca_cert': '',  # was installed
                'new_prometheus_ca_key': '',   # -------------
                'new_ca_cert': '',
                'new_ca_key': '',
                'new_external_ca_cert': '',
                'new_external_ca_key': '',
                'new_ldap_ca_cert': ''  # Relevant only if using LDAP
                 },
            'postgresql_server': {  # Relevant only if ssl_enabled==True
                'new_postgresql_server_cert': '',
                'new_postgresql_server_key': '',
                'new_postgresql_server_ca_cert': '',
                'new_postgresql_server_ca_key': ''
            },
            'rabbitmq': {  # Relevant only if specifying new_ca_cert
                'new_rabbitmq_cert': '',
                'new_rabbitmq_key': ''
            }
        }

    instances_ips = _get_instances_ips(client)
    return {
        'manager': {'cluster_members': [{
            'host_ip': str(host_ip),
            'new_internal_cert': '',
            'new_internal_key': '',
            'new_external_cert': '',
            'new_external_key': '',
            'new_postgresql_client_cert': '',
            'new_postgresql_client_key': '',
            'new_prometheus_cert': '',
            'new_prometheus_key': '',
            'new_prometheus_ca_cert': '',
            'new_prometheus_ca_key': ''
        } for host_ip in instances_ips['manager_ips']],
            'new_ca_cert': '',
            'new_ca_key': '',
            'new_external_ca_cert': '',
            'new_external_ca_key': '',
            'new_ldap_ca_cert': ''
        },
        'postgresql_server': {'cluster_members': [{
            'host_ip': str(host_ip),
            'new_cert': '',
            'new_key': '',
            'new_prometheus_cert': '',
            'new_prometheus_key': '',
            'new_prometheus_ca_cert': '',
            'new_prometheus_ca_key': ''
        } for host_ip in instances_ips['postgresql_ips']],
            'new_ca_cert': '',
            'new_ca_key': ''
        },
        'rabbitmq': {'cluster_members': [{
            'host_ip': str(host_ip),
            'new_cert': '',
            'new_key': '',
            'new_prometheus_cert': '',
            'new_prometheus_key': '',
            'new_prometheus_ca_cert': '',
            'new_prometheus_ca_key': ''
        } for host_ip in instances_ips['rabbitmq_ips']],
            'new_ca_cert': '',
            'new_ca_key': ''
        }
    }


def _get_instances_ips(client):
    return {'manager_ips': [manager.private_ip for manager in
                            client.manager.get_managers().items],
            'rabbitmq_ips': [broker.host for broker in
                             client.manager.get_brokers().items],
            'postgresql_ips': [db.host for db in
                               client.manager.get_db_nodes().items]
            }


def validate_config_dict(config_dict, is_all_in_one, logger):
    errors_list = []
    if is_all_in_one:
        validate_all_in_one_config_dict(errors_list, config_dict)
    else:
        _validate_instances(errors_list, config_dict)

    _check_path(errors_list, config_dict['manager'].get('new_ldap_ca_cert'))
    if errors_list:
        raise_errors_list(errors_list, logger)


def _validate_prometheus(errors_list, node):
    _validate_node_certs(errors_list, node,
                         'new_prometheus_cert', 'new_prometheus_key')
    ca_path_exists = _check_path(errors_list, node.get(
        'new_prometheus_ca_cert'))
    if ca_path_exists and not node.get('new_prometheus_cert'):
        errors_list.append('A new CA cert was specified for prometheus but '
                           'a new_cert was not.')


def validate_all_in_one_config_dict(errors_list, config_dict):
    manager_section = config_dict['manager']
    _validate_manager_node_cert_and_key(errors_list, manager_section)
    err_msg = 'A {0} was specified for manager but a {1} was not specified'
    if (manager_section.get('new_ca_cert') and
            (not manager_section.get('new_internal_cert'))):
        errors_list.append(err_msg.format('new_ca_cert', 'new_internal_cert'))

    if (manager_section.get('new_external_ca_cert') and
            (not manager_section.get('new_external_cert'))):
        errors_list.append(err_msg.format('new_external_ca_cert',
                                          'new_external_cert'))

    if (manager_section.get('new_ca_cert') and
            (not manager_section.get('new_postgresql_client_cert'))):
        errors_list.append(err_msg.format('new_ca_cert',
                                          'new_postgresql_client_cert'))

    postgresql_section = config_dict['postgresql_server']
    _validate_node_certs(errors_list, postgresql_section,
                         'new_postgresql_server_cert',
                         'new_postgresql_server_key')
    if (postgresql_section.get('new_postgresql_server_ca_cert') and
            (not postgresql_section.get('new_postgresql_server_cert'))):
        errors_list.append('A new_ca_cert was specified for postgresql_server '
                           'but a new_cert was not specified')

    rabbitmq_section = config_dict['rabbitmq']
    _validate_node_certs(errors_list, rabbitmq_section,
                         'new_rabbitmq_cert', 'new_rabbitmq_key')
    if (manager_section.get('new_rabbitmq_ca_cert') and
            (not rabbitmq_section.get('new_rabbitmq_cert'))):
        errors_list.append('A new_ca_cert was specified for manager '
                           'but a new_cert was not specified for rabbitmq')


def _validate_username_and_private_key():
    if (not env.profile.ssh_user) or (not env.profile.ssh_key):
        raise CloudifyCliError('Please configure the profile ssh-key and '
                               'ssh-user using the `cfy profiles set` command')


def _validate_instances(errors_list, config_dict):
    for instance in 'postgresql_server', 'rabbitmq':
        _validate_cert_and_key(errors_list,
                               config_dict[instance]['cluster_members'])
        _validate_new_ca_cert(errors_list, config_dict, instance)

    _validate_manager_cert_and_key(errors_list,
                                   config_dict['manager']['cluster_members'])
    _validate_new_manager_ca_certs(errors_list, config_dict)


def _validate_new_ca_cert(errors_list, config_dict, instance_name):
    _validate_ca_cert(errors_list, config_dict[instance_name], instance_name,
                      'new_ca_cert', 'new_cert',
                      config_dict[instance_name]['cluster_members'])


def _validate_new_manager_ca_certs(errors_list, config_dict):
    _validate_ca_cert(errors_list, config_dict['manager'], 'manager',
                      'new_ca_cert', 'new_internal_cert',
                      config_dict['manager']['cluster_members'])
    _validate_ca_cert(errors_list, config_dict['manager'],
                      'manager', 'new_external_ca_cert',
                      'new_external_cert',
                      config_dict['manager']['cluster_members'])
    _validate_ca_cert(errors_list, config_dict['postgresql_server'],
                      'postgresql_server', 'new_ca_cert',
                      'new_postgresql_client_cert',
                      config_dict['manager']['cluster_members'])


def _validate_ca_cert(errors_list, instance, instance_name, new_ca_cert_name,
                      cert_name, cluster_members):
    """Validates the CA cert.

    Validates that the CA path is valid, and if it is, then a new cert was
    specified for all cluster members.
    """
    err_msg = '{0} was specified for instance {1}, but {2} was not specified' \
              ' for all cluster members.'.format(new_ca_cert_name,
                                                 instance_name,
                                                 cert_name)

    new_ca_cert_path = instance.get(new_ca_cert_name)
    if _check_path(errors_list, new_ca_cert_path):
        if not all(member.get(cert_name) for member in cluster_members):
            errors_list.append(err_msg)


def _validate_cert_and_key(errors_list, nodes):
    for node in nodes:
        _validate_node_certs(errors_list, node, 'new_cert', 'new_key')
        _validate_prometheus(errors_list, node)


def _validate_manager_cert_and_key(errors_list, nodes):
    for node in nodes:
        _validate_manager_node_cert_and_key(errors_list, node)


def _validate_manager_node_cert_and_key(errors_list, node):
    _validate_node_certs(errors_list, node,
                         'new_internal_cert',
                         'new_internal_key')
    _validate_node_certs(errors_list, node,
                         'new_external_cert',
                         'new_external_key')
    _validate_node_certs(errors_list, node,
                         'new_postgresql_client_cert',
                         'new_postgresql_client_key')
    _validate_prometheus(errors_list, node)


def _validate_node_certs(errors_list, certs_dict, new_cert_name, new_key_name):
    new_cert_path = certs_dict.get(new_cert_name)
    new_key_path = certs_dict.get(new_key_name)
    if bool(new_key_path) != bool(new_cert_path):
        host_ip = certs_dict.get('host_ip') or env.profile.manager_ip
        errors_list.append('Either both {0} and {1} must be '
                           'provided, or neither for host '
                           '{2}'.format(new_cert_name, new_key_name, host_ip))
    _check_path(errors_list, new_cert_path)
    _check_path(errors_list, new_key_path)


def _check_path(errors_list, path):
    if path:
        if os.path.exists(os.path.expanduser(path)):
            return True
        errors_list.append('The path {0} does not exist'.format(path))
    return False


def raise_errors_list(errors_list, logger):
    logger.info(_errors_list_str(errors_list))
    raise CloudifyCliError()


def _errors_list_str(errors_list):
    err_str = 'Errors:\n'
    err_lst = '\n'.join(' [{0}] {1}'.format(i+1, err) for i, err
                        in enumerate(errors_list))
    return err_str + err_lst
