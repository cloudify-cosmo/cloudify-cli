import asyncio
import json

import click

from ..cli import cfy, helptexts
from ..exceptions import CloudifyCliError
from ..logger import get_global_json_output
from ..table import print_data
from ..utils import before_to_utc_timestamp

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
@click.option('-i', '--since',
              help=helptexts.AUDIT_SINCE)
@click.option('-f', '--follow', '--tail',
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
    since_timestamp = before_to_utc_timestamp(since) if since else None
    if follow:
        loop = asyncio.get_event_loop()
        if not loop:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _stream_logs(creator_name,
                         execution_id,
                         since_timestamp,
                         timeout,
                         logger,
                         client))
        loop.close()
    else:
        _list_logs(creator_name,
                   execution_id,
                   since_timestamp,
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


async def _stream_logs(creator_name,
                       execution_id,
                       since,
                       timeout,
                       logger,
                       client):
    if not hasattr(client.auditlog, 'stream'):
        raise CloudifyCliError('Streaming endpoint client not available. '
                               'Consider upgrading your installation to one '
                               'based on Python>=3.6.')
    logger.info('Streaming audit log entries...')
    response = await client.auditlog.stream(timeout=timeout,
                                            creator_name=creator_name,
                                            execution_id=execution_id,
                                            since=since)
    async for data in response.content:
        for audit_log in _streamed_audit_log(data):
            if get_global_json_output():
                print(audit_log)
            else:
                print(_format_audit_log(audit_log))


def _streamed_audit_log(data):
    line = data.strip().decode(errors='ignore')
    if line:
        yield json.loads(line)


def _format_audit_log(data):
    result = f"[{data['created_at']}]"
    if 'creator_name' in data and data['creator_name']:
        result = f"{result} user {data['creator_name']}"
    if 'execution_id' in data and data['execution_id']:
        result = f"{result} execution {data['execution_id']}"
    result = f"{result} {data['operation'].upper()}D"
    result = f"{result} {data['ref_table']} {data['ref_id']}"
    return result


@auditlog.command(name='truncate',
                  short_help='Truncate audit log')
@click.option('-b', '--before',
              required=True,
              help=helptexts.AUDIT_TRUNCATE_BEFORE)
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
    before_timestamp = before_to_utc_timestamp(before)
    if before_timestamp is None:
        raise CloudifyCliError('Failed to parse timestamp: {0}'
                               .format(before))

    logger.info("Truncating audit log entries...")
    params = {'before': before_timestamp.isoformat()}
    if creator_name:
        params.update({'creator_name': creator_name})
    if execution_id:
        params.update({'execution_id': execution_id})
    result = client.auditlog.delete(**params)
    logger.info('%d audit log entries have been truncated', result.deleted)
