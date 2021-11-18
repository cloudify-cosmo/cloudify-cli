import re
from datetime import datetime, timedelta

import click

from cloudify._compat import PY2

from ..cli import cfy, helptexts
from ..exceptions import CloudifyCliError
from ..table import print_data

AUDITLOG_COLUMNS = ['ref_table', 'ref_id', 'operation', 'creator_name',
                    'execution_id', 'created_at']


def _parse_before(ctx, spec):
    """Parse the --before/--since parameter"""
    if not spec:
        return spec
    if spec == "now":
        return datetime.utcnow()
    r = re.match(r'^([.\d]+)([hdw])$', spec, re.IGNORECASE)
    if r:
        # timestamp specification e.g. 10.5h, 15d, 7w
        count, unit = float(r.groups()[0]), r.groups()[1].lower()
        if unit == 'h':
            delta = timedelta(hours=count)
        elif unit == 'd':
            delta = timedelta(days=count)
        else:  # 'w'
            delta = timedelta(weeks=count)
        return datetime.utcnow() - delta
    elif spec.startswith('@'):
        try:
            return datetime.utcfromtimestamp(int(spec[1:]))
        except ValueError:
            raise CloudifyCliError('Failed to parse timestamp: {0}'
                                   .format(spec))
    else:
        return spec


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
@click.option('-i', '--since',
              help=helptexts.AUDIT_SINCE,
              callback=_parse_before)
@click.option('-f', '--follow',
              help=helptexts.AUDIT_FOLLOW,
              is_flag=True)
@cfy.options.timeout(default=300)
@cfy.options.sort_by()
@cfy.options.descending
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.options.common_options
@cfy.pass_logger
@cfy.pass_client()
def list_logs(creator_name,
              execution_id,
              since,
              follow,
              timeout,
              sort_by,
              descending,
              pagination_offset,
              pagination_size,
              logger,
              client,
              ):
    if follow:
        if PY2:
            raise CloudifyCliError('Streaming requires Python>=3.6.')
        from ..async_commands.audit_log import stream_logs
        stream_logs(creator_name,
                    execution_id,
                    since,
                    timeout,
                    logger,
                    client)
    else:
        _list_logs(creator_name,
                   execution_id,
                   since,
                   sort_by,
                   descending,
                   pagination_offset,
                   pagination_size,
                   logger,
                   client)


def _list_logs(creator_name,
               execution_id,
               since,
               sort_by,
               descending,
               pagination_offset,
               pagination_size,
               logger,
               client):
    """List audit_log entries"""
    logger.info('Listing audit log entries...')
    logs = client.auditlog.list(
        creator_name=creator_name,
        execution_id=execution_id,
        since=since,
        order_by=sort_by,
        desc=descending,
        offset=pagination_offset,
        size=pagination_size,
    )
    print_data(AUDITLOG_COLUMNS, logs, 'AuditLogs:')
    logger.info('Showing %d of %d audit log entries',
                len(logs), logs.metadata.pagination.total)


@auditlog.command(name='truncate',
                  short_help='Truncate audit log')
@click.option('-b', '--before',
              required=True,
              help=helptexts.AUDIT_TRUNCATE_BEFORE,
              callback=_parse_before)
@click.option('-c', '--creator-name',
              help=helptexts.AUDIT_CREATOR_NAME)
@click.option('-e', '--execution-id',
              help=helptexts.AUDIT_EXECUTION_ID)
@cfy.pass_logger
@cfy.pass_client()
def truncate_logs(before,
                  creator_name,
                  execution_id,
                  logger,
                  client
                  ):
    """Truncate audit_log entries"""
    logger.info("Truncating audit log entries...")
    params = {'before': before}
    if creator_name:
        params.update({'creator_name': creator_name})
    if execution_id:
        params.update({'execution_id': execution_id})
    result = client.auditlog.delete(**params)
    logger.info('%d audit log entries have been truncated', result.deleted)
