import asyncio
import json

import aiohttp.client_exceptions

from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.logger import get_global_json_output


def stream_logs(creator_name,
                execution_id,
                since,
                timeout,
                logger,
                client):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_stream_logs(creator_name,
                                         execution_id,
                                         since,
                                         timeout,
                                         logger,
                                         client))
    loop.close()


async def _stream_logs(creator_name,
                       execution_id,
                       since,
                       timeout,
                       logger,
                       client):
    if not hasattr(client.auditlog, 'stream'):
        raise CloudifyCliError('Streaming requires Python>=3.6.')
    logger.info('Streaming audit log entries...')
    async with client.auditlog as auditlog:
        response = await auditlog.stream(
            timeout=timeout,
            creator_name=creator_name,
            execution_id=execution_id,
            since=since
        )
        try:
            async for data in response.content:
                for audit_log in _streamed_audit_log(data):
                    if get_global_json_output():
                        print(audit_log)
                    else:
                        print(_format_audit_log(audit_log))
        except aiohttp.client_exceptions.ClientError as e:
            raise CloudifyCliError(
                f'Error getting audit log stream: {e}'
            ) from e


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
