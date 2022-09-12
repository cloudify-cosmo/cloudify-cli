from cloudify_cli.cli import cfy
from cloudify_cli.exceptions import CloudifyCliError


@cfy.group(name='ldap')
@cfy.options.common_options
@cfy.assert_manager_active()
def ldap():
    """Set LDAP authenticator.
    """
    pass


@ldap.command(name='set',
              short_help='Set the manager to use the LDAP authenticator.')
@cfy.options.ldap_server
@cfy.options.ldap_username
@cfy.options.ldap_password
@cfy.options.ldap_domain
@cfy.options.ldap_is_active_directory
@cfy.options.ldap_dn_extra
@cfy.options.ldap_ca_path
@cfy.options.ldap_base_dn
@cfy.options.ldap_group_dn
@cfy.options.ldap_bind_format
@cfy.options.ldap_user_filter
@cfy.options.ldap_group_member_filter
@cfy.options.ldap_attribute_email
@cfy.options.ldap_attribute_first_name
@cfy.options.ldap_attribute_last_name
@cfy.options.ldap_attribute_uid
@cfy.options.ldap_attribute_group_membership
@cfy.options.ldap_nested_levels
@cfy.pass_client()
@cfy.pass_logger
def set(ldap_server,
        ldap_username,
        ldap_password,
        ldap_domain,
        ldap_is_active_directory,
        ldap_dn_extra,
        ldap_base_dn,
        ldap_group_dn,
        ldap_bind_format,
        ldap_user_filter,
        ldap_group_member_filter,
        ldap_attribute_email,
        ldap_attribute_first_name,
        ldap_attribute_last_name,
        ldap_attribute_uid,
        ldap_attribute_group_membership,
        ldap_nested_levels,
        ldap_ca_path,
        client,
        logger):
    if (ldap_username and not ldap_password) \
            or (ldap_password and not ldap_username):
        raise CloudifyCliError(
            'Must either set both username and password, or neither. '
            'Note that an empty username or password is invalid')
    logger.info('Setting the Cloudify manager authenticator to use LDAP..')
    client.ldap.set(ldap_server=ldap_server,
                    ldap_username=ldap_username,
                    ldap_password=ldap_password,
                    ldap_is_active_directory=ldap_is_active_directory,
                    ldap_domain=ldap_domain,
                    ldap_dn_extra=ldap_dn_extra,
                    ldap_base_dn=ldap_base_dn,
                    ldap_group_dn=ldap_group_dn,
                    ldap_bind_format=ldap_bind_format,
                    ldap_user_filter=ldap_user_filter,
                    ldap_group_member_filter=ldap_group_member_filter,
                    ldap_attribute_email=ldap_attribute_email,
                    ldap_attribute_first_name=ldap_attribute_first_name,
                    ldap_attribute_last_name=ldap_attribute_last_name,
                    ldap_attribute_uid=ldap_attribute_uid,
                    ldap_attribute_group_membership=(
                        ldap_attribute_group_membership
                    ),
                    ldap_nested_levels=ldap_nested_levels,
                    ldap_ca_path=ldap_ca_path)
    logger.info('LDAP authentication set successfully')


@ldap.command(name='status',
              short_help='Get the manager LDAP status (enabled/disabled).')
@cfy.pass_client()
@cfy.pass_logger
def status(client, logger):
    logger.info(client.ldap.get_status())
