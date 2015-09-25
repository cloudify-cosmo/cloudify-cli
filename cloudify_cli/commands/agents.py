########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import threading

from cloudify_cli import utils
from cloudify_cli.logger import (get_logger, get_events_logger)
from cloudify_cli.execution_events_fetcher import wait_for_execution
from cloudify_cli.exceptions import SuppressedCloudifyCliError
from cloudify_cli.exceptions import ExecutionTimeoutError
from cloudify import logs


def install(deployment_id, include_logs):
    workflow_id = 'install_new_agents'
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    if deployment_id:
        logger.info("Installing agent for deployment '{0}'"
                    .format(deployment_id))
        try:
            execution = client.executions.start(
                deployment_id,
                workflow_id,
            )

            execution = wait_for_execution(
                client,
                execution,
                events_handler=get_events_logger(),
                include_logs=include_logs,
                timeout=900
            )

            if execution.error:
                logger.info("Execution of workflow '{0}' for "
                            "deployment '{1}' failed. [error={2}]"
                            .format(workflow_id, deployment_id,
                                    execution.error))
            else:
                logger.info("Finished executing workflow "
                            "'{0}' on deployment"
                            " '{1}'".format(workflow_id, deployment_id))

        except ExecutionTimeoutError as e:
            logger.info("Execution of workflow '{0}' "
                        "for deployment '{1}' timed out. "
                        "* Run 'cfy executions cancel "
                        "--execution-id {2}' to cancel"
                        " the running workflow."
                        .format(workflow_id, deployment_id, e.execution_id))

            raise SuppressedCloudifyCliError()
    else:
        logger.info('Installing agents for all deployments')
        deps = client.deployments.list()

        error_summary = []
        error_summary_lock = threading.Lock()

        event_lock = threading.Lock()

        def log_to_summary(message):
            with error_summary_lock:
                error_summary.append(message)

        def threadsafe_log(message):
            with event_lock:
                logger.info(message)

        def threadsafe_events_logger(events):
            with event_lock:
                for event in events:
                    logger.info(logs.create_event_message_prefix(event))

        def worker(dep_id):
            try:
                execution = client.executions.start(
                    dep_id,
                    workflow_id,
                )

                execution = wait_for_execution(
                    client,
                    execution,
                    events_handler=threadsafe_events_logger,
                    include_logs=include_logs,
                    timeout=900
                )

                if execution.error:
                    log_to_summary("Execution of workflow '{0}' for "
                                   "deployment '{1}' failed. [error={2}]"
                                   .format(workflow_id,
                                           dep_id,
                                           execution.error))
                else:
                    threadsafe_log("Finished executing workflow "
                                   "'{0}' on deployment"
                                   " '{1}'".format(workflow_id, dep_id))

            except ExecutionTimeoutError as e:
                log_to_summary("Execution of workflow '{0}' "
                               "for deployment '{1}' timed out. "
                               "* Run 'cfy executions cancel "
                               "--execution-id {2}' to cancel"
                               " the running workflow."
                               .format(
                                    workflow_id,
                                    deployment_id,
                                    e.execution_id
                               ))

        threads = [threading.Thread(target=worker, args=(dep.id,))
                   for dep in deps]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if error_summary:
            logger.info('Summary:\n{0}\n'.format(
                '\n'.join(error_summary)
            ))
