import os

from cloudify_cli.cli import cfy
from cloudify_cli.logger import output
from cloudify_cli.table import print_data
from cloudify_cli.exceptions import CloudifyValidationError

LICENSE_COLUMN = ['customer_id', 'expiration_date', 'license_edition', 'trial',
                  'cloudify_version', 'capabilities', 'expired']
ENVIRONMENT_COLUMNS = ['id', 'display_name', 'tenant_name']
ENVIRONMENT_LABELS = {'id': 'deployment_id', 'display_name': 'deployment_name'}


@cfy.group(name='license')
@cfy.options.common_options
@cfy.assert_manager_active()
def license():
    """ Handle Cloudify licenses
    """
    pass


@license.command(
    name='check',
    short_help='Checks the manager license state is healthy.')
@cfy.assert_manager_active()
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def check(logger, client):
    logger.info('Checking manager license state.')
    client.license.check()
    logger.info('Manager is licensed.')


@license.command(
    name='list',
    short_help='Get the Cloudify license that was uploaded to this Manager')
@cfy.assert_manager_active()
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def list(logger, client):
    """Returns the Cloudify license from the Manager.
    """
    logger.info('Retrieving Cloudify License')
    license = client.license.list()
    print_data(LICENSE_COLUMN, license, 'Cloudify License')


@license.command(
    name='upload',
    short_help='Upload a new Cloudify license to the Manager')
@cfy.argument('license-path')
@cfy.assert_manager_active()
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def upload(logger, client, license_path):
    logger.info('Uploading Cloudify License `{0}` to the Manager...'.
                format(license_path))
    if not os.path.isfile(license_path):
        raise CloudifyValidationError('License file was not found in the '
                                      'following path: `{0}`'.
                                      format(license_path))
    client.license.upload(license_path)
    logger.info('Cloudify license successfully uploaded.')


@license.command(
    name='remove',
    short_help='Remove a Cloudify license from the Manager')
@cfy.assert_manager_active()
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def remove(logger, client):
    logger.info('Removing Cloudify License from the Manager...')
    client.license.delete()
    logger.info('Cloudify license successfully removed.')


@license.group(name='environments')
@cfy.options.common_options
@cfy.assert_manager_active()
def environments():
    """Handle licensed environments on the manager
    """
    pass


@environments.command(name='list',
                      short_help='List all licensed environments')
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def environments_list(sort_by,
                      descending,
                      pagination_offset,
                      pagination_size,
                      logger,
                      client):
    """List all licensed environments on the manager.
    """
    logger.info('Listing all licensed environments...')

    environments = client.deployments.list(sort=sort_by,
                                           is_descending=descending,
                                           _offset=pagination_offset,
                                           _size=pagination_size,
                                           _all_tenants=True,
                                           _environments_only=True)
    print_data(ENVIRONMENT_COLUMNS, environments, 'Environments:',
               labels=ENVIRONMENT_LABELS)
    logger.info('Showing %d of %d environments',
                len(environments), environments.metadata.pagination.total)


@environments.command(name='count',
                      short_help='Print the count of licensed environments')
@cfy.options.common_options
@cfy.pass_logger
@cfy.pass_client()
def environments_count(logger, client):
    """Print the count of licensed environments on the manager.
    """
    environments = client.deployments.list(_all_tenants=True,
                                           _get_all_results=True,
                                           _environments_only=True)
    output('Licensed environments count: {}'.format(len(environments)))
