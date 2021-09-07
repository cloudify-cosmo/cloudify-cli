import click

from ..cli import cfy, helptexts
from ..table import print_data

AUDITLOG_COLUMNS = ['ref_table', 'ref_id', 'operation', 'creator_name',
                    'execution_id', 'created_at']


@cfy.group(name='auditlog')
@cfy.assert_manager_active()
def auditlog():
    """Manage the audit log"""
    pass


@auditlog.command(name='list',
                  short_help='List audit log entries')
@click.option('-c', '--creator-name',
              help=helptexts.AUDIT_CREATOR_NAME)
@click.option('-e', '--execution-id',
              help=helptexts.AUDIT_EXECUTION_ID)
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.pass_logger
@cfy.pass_client()
def list_logs(creator_name,
              execution_id,
              sort_by,
              descending,
              pagination_offset,
              pagination_size,
              logger,
              client,
              ):
    """List audit_log entries"""
    logger.info('Listing audit log entries...')
    logs = client.auditlog.list(
        creator_name=creator_name,
        execution_id=execution_id,
        order_by=sort_by,
        desc=descending,
        offset=pagination_offset,
        size=pagination_size,
    )
    print_data(AUDITLOG_COLUMNS, logs, 'AuditLogs:')
    logger.info('Showing %d of %d audit log entries',
                len(logs), logs.metadata.pagination.total)
