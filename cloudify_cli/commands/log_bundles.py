from .. import utils
from ..table import print_data
from ..cli import cfy

LOG_BUNDLE_COLUMNS = ['id', 'created_at', 'status', 'error',
                      'visibility', 'tenant_name', 'created_by']


@cfy.group(name='log_bundles')
@cfy.options.common_options
@cfy.assert_manager_active()
def log_bundles():
    """Handle manager log bundles."""


@log_bundles.command(name='create',
                     short_help='Create a log bundle [manager only]')
@cfy.argument('log-bundle-id', required=False, callback=cfy.validate_name)
@cfy.options.common_options
@cfy.options.queue_log_bundle
@cfy.pass_client()
@cfy.pass_logger
def create(log_bundle_id,
           queue,
           logger,
           client):
    """Create a log bundle on the manager

    The log bundle will contain all cloudify logs it was able to retrieve from
    all managers, brokers, and database nodes it was able to reach.

    `LOG_BUNDLE_ID` is the id to attach to the log bundle.
    """
    log_bundle_id = log_bundle_id or utils.generate_suffixed_id('log_bundle')
    logger.info('Creating log_bundle {0}...'.format(log_bundle_id))

    execution = client.log_bundles.create(log_bundle_id, queue)
    started_log_msg = "Started workflow execution. The execution's id is" \
                      " {0}.".format(execution.id)
    queued_log_msg = '`queue` flag was passed, log bundle creation will' \
                     ' start automatically when possible. Execution id:' \
                     ' {0}'.format(execution.id)
    queued = True if execution.status == 'queued' else False
    logger.info(queued_log_msg) if queued else logger.info(started_log_msg)


@log_bundles.command(name='delete',
                     short_help='Delete a log bundle [manager only]')
@cfy.argument('log-bundle-id')
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def delete(log_bundle_id, logger, client):
    """Delete a log_bundle from the manager

    `LOG_BUNDLE_ID` is the id of the log bundle to delete.
    """
    logger.info('Deleting log_bundle {0}...'.format(log_bundle_id))
    client.log_bundles.delete(log_bundle_id)
    logger.info('Log bundle deleted successfully')


@log_bundles.command(name='download',
                     short_help='Download a log bundle [manager only]')
@cfy.argument('log-bundle-id')
@cfy.options.output_path
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def download(log_bundle_id, output_path, logger, client):
    """Download a log bundle from the manager

    `LOG_BUNDLE_ID` is the id of the log bundle to download.
    """
    logger.info('Downloading log_bundle {0}...'.format(log_bundle_id))
    log_bundle_name = output_path if output_path else log_bundle_id
    progress_handler = utils.generate_progress_handler(log_bundle_name, '')
    target_file = client.log_bundles.download(log_bundle_id,
                                              output_path,
                                              progress_handler)
    logger.info('Log bundle downloaded as {0}'.format(target_file))


@log_bundles.command(name='list',
                     short_help='List log bundles [manager only]')
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def list(sort_by,
         descending,
         search,
         pagination_offset,
         pagination_size,
         logger,
         client):
    """List all log bundles on the manager"""
    logger.info('Listing log_bundles...')
    log_bundles = client.log_bundles.list(
        sort=sort_by,
        is_descending=descending,
        _search=search,
        _offset=pagination_offset,
        _size=pagination_size)

    print_data(LOG_BUNDLE_COLUMNS, log_bundles, 'Log bundles:')
    total = log_bundles.metadata.pagination.total
    logger.info(
        'Showing {0} of {1} log_bundles'.format(len(log_bundles), total))
