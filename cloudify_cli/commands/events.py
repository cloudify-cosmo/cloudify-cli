########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

"""
Handles all commands that start with 'cfy events'
"""

from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.execution_events_fetcher import ExecutionEventsFetcher
from cloudify_cli.logger import get_logger
from cloudify_cli.logger import get_events_logger
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_cli import utils


def ls(execution_id, include_logs):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info("Getting events from management server {0} for "
                "execution id '{1}' "
                "[include_logs={2}]".format(management_ip,
                                            execution_id,
                                            include_logs))
    client = utils.get_rest_client(management_ip)
    try:

        execution_events = ExecutionEventsFetcher(
            client,
            execution_id,
            include_logs=include_logs)
        events = execution_events.fetch_all()
        events_logger = get_events_logger()
        events_logger(events)
        logger.info('\nTotal events: {0}'.format(len(events)))
    except CloudifyClientError, e:
        if e.status_code != 404:
            raise
        msg = ("Execution '{0}' not found on management server"
               .format(execution_id))
        raise CloudifyCliError(msg)
