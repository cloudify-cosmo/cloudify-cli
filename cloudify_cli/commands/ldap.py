########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
from ..cli import cfy


@cfy.group(name='ldap')
@cfy.options.verbose()
@cfy.assert_manager_active()
def ldap():
    """Set LDAP authenticator.
    """
    pass


@ldap.command(name='set',
              short_help='Set the manager to use the LDAP authenticator.')
@cfy.options.ldap_server()
@cfy.options.ldap_username()
@cfy.options.ldap_password()
@cfy.options.ldap_domain()
@cfy.options.ldap_is_active_directory()
@cfy.options.ldap_dn_extra()
@cfy.pass_client()
@cfy.pass_logger
def set(ldap_server,
        ldap_username,
        ldap_password,
        ldap_domain,
        ldap_is_active_directory,
        ldap_dn_extra,
        client,
        logger):
    logger.info('Setting the Cloudify manager authenticator to use LDAP..')
    client.ldap.set(ldap_server=ldap_server,
                    ldap_username=ldap_username,
                    ldap_password=ldap_password,
                    ldap_is_active_directory=ldap_is_active_directory,
                    ldap_domain=ldap_domain,
                    ldap_dn_extra=ldap_dn_extra)
    logger.info('LDAP authentication set successfully')


@ldap.command(name='status',
              short_help='Get the manager LDAP status (enabled/disabled).')
@cfy.pass_client()
@cfy.pass_logger
def status(client, logger):
    logger.info(client.ldap.get_status())
