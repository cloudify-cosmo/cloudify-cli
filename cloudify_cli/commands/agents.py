########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

import os.path
import threading
import time

try:
    import queue    # Python 3.x
except ImportError:
    import Queue as queue

from cloudify.logs import create_event_message_prefix

from cloudify_cli import env, utils
from cloudify_cli.cli import cfy
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.execution_events_fetcher import (
    wait_for_execution,
    WAIT_FOR_EXECUTION_SLEEP_INTERVAL)
from cloudify_cli.table import print_data


_NODE_INSTANCE_STATE_STARTED = 'started'
AGENT_COLUMNS = ['id', 'ip', 'deployment', 'state', 'node', 'system',
                 'version', 'install_method', 'tenant_name']

MAX_TRACKER_THREADS = 20


@cfy.group(name='agents')
@cfy.options.common_options
@cfy.assert_manager_active()
def agents():
    """Handle a deployment's agents
    """
    pass


@agents.command(name='list',
                short_help='List installed agents [manager only]')
@cfy.options.common_options
@cfy.options.tenant_name(required=False,
                         mutually_exclusive_with=['all_tenants'],
                         resource_name_for_help='relevant deployment(s)')
@cfy.options.agent_filters
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
@cfy.options.extended_view
def agents_list(agent_filters, tenant_name, client, logger, all_tenants):
    utils.explicit_tenant_name_message(tenant_name, logger)
    agent_filters['_all_tenants'] = all_tenants
    agent_list = client.agents.list(**agent_filters)
    logger.info('Listing agents...')
    print_data(AGENT_COLUMNS, agent_list, 'Agents:')


@agents.command(name='install',
                short_help='Install deployment agents [manager only]')
@cfy.options.common_options
@cfy.options.tenant_name(required=False,
                         mutually_exclusive_with=['all_tenants'],
                         resource_name_for_help='relevant deployment(s)')
@cfy.options.all_tenants
@cfy.options.stop_old_agent
@cfy.options.manager_ip
@cfy.options.manager_certificate
@cfy.options.agent_filters
@cfy.options.agents_wait
@cfy.options.install_agent_timeout
@cfy.pass_logger
@cfy.pass_client()
def install(agent_filters,
            tenant_name,
            logger,
            client,
            all_tenants,
            stop_old_agent,
            manager_ip,
            manager_certificate,
            wait,
            install_agent_timeout):
    """Install agents on the hosts of existing deployments.
    """
    if manager_certificate:
        manager_certificate = _validate_certificate_file(manager_certificate)
    params = dict()
    # We only want to pass this arg if it's true, because of backwards
    # compatibility with blueprints that don't support it
    if stop_old_agent:
        params['stop_old_agent'] = stop_old_agent
    if manager_ip or manager_certificate:
        params['manager_ip'] = manager_ip
        params['manager_certificate'] = manager_certificate
    params['install_agent_timeout'] = install_agent_timeout
    utils.explicit_tenant_name_message(tenant_name, logger)
    get_deployments_and_run_workers(
        client, agent_filters, all_tenants,
        logger, 'install_new_agents', wait, params)


def get_filters_map(
        client,
        logger,
        agent_filters,
        all_tenants):
    # We need to analyze the filters.
    #
    # If node instance ID's are given, then we only process these node
    # instances. The filters for deployment ID's and node ID's
    # must not be specified.
    #
    # Otherwise, we perform an intersection between:
    #
    # * Union of all specified node ID's
    # * Union of all specified deployment ID's
    #
    # This will end up being a mapping of this form:
    #
    # tenant1 |- dep1 |- nodeinstance_1
    #         |-      |- nodeinstance_2
    #         |-      |- nodeinstance_3
    # tenant2 |- dep2 |- nodeinstance_4
    #         |- dep3 |- nodeinstance_5
    #         |-      |- nodeinstance_6
    #
    # It is possible that one of the keys in the dict is 'None',
    # and that means - the current tenant.

    if agent_filters[cfy.AGENT_FILTER_NODE_INSTANCE_IDS] and (
            agent_filters[cfy.AGENT_FILTER_DEPLOYMENT_ID] or
            agent_filters[cfy.AGENT_FILTER_NODE_IDS]):
        raise CloudifyCliError(
            "If node instance ID's are provided, neither deployment ID's nor "
            "deployment ID's are allowed.")
    tenants_to_deployments = dict()

    requested_node_instance_ids = agent_filters[
        cfy.AGENT_FILTER_NODE_INSTANCE_IDS]
    if requested_node_instance_ids:
        candidate_ids = requested_node_instance_ids
        candidates = client.node_instances.list(
            id=candidate_ids,
            _include=['id', 'tenant_name', 'deployment_id'],
            _get_all_results=True, _all_tenants=True)

        # Ensure that all requested node instance ID's actually exist.
        missing = set(candidate_ids) - set([
            node_instance.id for node_instance in candidates])
        if missing:
            raise CloudifyCliError("Node instances do not exist: "
                                   "%s" % ', '.join(missing))

        for node_instance in candidates:
            tenant_map = tenants_to_deployments.setdefault(
                node_instance['tenant_name'], dict())
            deployment = tenant_map.setdefault(
                node_instance['deployment_id'], dict())
            deployment_node_instances = deployment.setdefault(
                'node_instance_ids', list())
            deployment_node_instances.append(node_instance.id)
    else:
        requested_deployment_ids = agent_filters[
            cfy.AGENT_FILTER_DEPLOYMENT_ID]
        requested_node_ids = agent_filters[cfy.AGENT_FILTER_NODE_IDS]

        existing_deployments = client.deployments.list(
            id=requested_deployment_ids or None,
            _include=['id', 'tenant_name'],
            _get_all_results=True,
            _all_tenants=all_tenants)

        # If at least one deployment ID was provided, then ensure
        # all specified deployment ID's indeed exist.
        if requested_deployment_ids:
            missing = set(requested_deployment_ids) - set([
                deployment.id for deployment in existing_deployments])
            if missing:
                raise CloudifyCliError("Deployments do not exist: "
                                       "%s" % ', '.join(missing))

        if requested_node_ids:
            existing_nodes = client.nodes.list(
                id=requested_node_ids,
                _include=['id', 'deployment_id', 'tenant_name'],
                _get_all_results=True,
                _all_tenants=all_tenants
            )
            deps_with_req_nodes = set([
                (node['tenant_name'], node.deployment_id)
                for node in existing_nodes])
            # Collect all deployments (from 'existing_deployments')
            # that includes at least one of the requested nodes.
            deployments_to_execute = list()
            for deployment in existing_deployments:
                if (deployment['tenant_name'], deployment.id) in \
                        deps_with_req_nodes:
                    deployments_to_execute.append(deployment)
        else:
            deployments_to_execute = existing_deployments

        for deployment in deployments_to_execute:
            tenant_map = tenants_to_deployments.setdefault(
                deployment['tenant_name'], dict())
            deployment_filters = tenant_map.setdefault(deployment.id, dict())
            if requested_node_ids:
                deployment_filters['node_ids'] = requested_node_ids

        # If no deployment ID's were requested, then filter out deployments
        # that have at least one Compute instance that is not in "started"
        # state.
        # We skip this check if specific deployment ID's were requested.
        if not requested_deployment_ids:
            for tenant_name in list(tenants_to_deployments):
                tenant_client = env.get_rest_client(tenant_name=tenant_name)
                deps_to_execute = tenants_to_deployments[tenant_name]
                offset = 0
                while True:
                    node_instances = tenant_client.node_instances.list(
                        _include=['id', 'host_id', 'deployment_id', 'state'],
                        _offset=offset,
                    )
                    # Find all unstarted Compute instances.
                    unstarted_computes = [
                        ni for ni in node_instances
                        if ni.id == ni.host_id and
                        ni.state != _NODE_INSTANCE_STATE_STARTED
                    ]

                    for unstarted_ni in unstarted_computes:
                        logger.info("Node instance '%s' is not in '%s' state; "
                                    "deployment '%s' will be skipped",
                                    unstarted_ni.id,
                                    _NODE_INSTANCE_STATE_STARTED,
                                    unstarted_ni.deployment_id)
                        deps_to_execute.pop(unstarted_ni.deployment_id, None)

                    if not deps_to_execute:
                        del tenants_to_deployments[tenant_name]

                    size = node_instances.metadata.pagination.size
                    total = node_instances.metadata.pagination.total
                    if len(node_instances) < size or size == total:
                        break
                    offset += size

    return tenants_to_deployments


def get_deployments_and_run_workers(
        client,
        agent_filters,
        all_tenants,
        logger,
        workflow_id,
        agents_wait,
        parameters=None):
    tenants_to_deployments = get_filters_map(
        client, logger, agent_filters, all_tenants)
    if not tenants_to_deployments:
        raise CloudifyCliError("No eligible deployments found")

    started_executions = []
    requested_install_methods = agent_filters[cfy.AGENT_FILTER_INSTALL_METHODS]
    for tenant_name, deployments in tenants_to_deployments.items():
        tenant_client = env.get_rest_client(tenant_name=tenant_name)
        for deployment_id, dep_filters in deployments.items():
            execution_params = dep_filters.copy()   # Shallow is fine.
            if requested_install_methods:
                execution_params['install_methods'] = requested_install_methods
            if parameters:
                execution_params.update(parameters)
            execution = tenant_client.executions.start(
                deployment_id, workflow_id, execution_params,
                allow_custom_parameters=True)
            started_executions.append((tenant_name, execution))
            logger.info(
                "Started execution for deployment '%s' on tenant '%s': %s",
                deployment_id, tenant_name, execution.id
            )

    if not agents_wait:
        logger.info("Executions started for all applicable deployments. "
                    "You may now use the 'cfy events list' command to "
                    "view the events associated with these executions.")
        return

    executions_queue = queue.Queue()
    for execution_info in started_executions:
        executions_queue.put(execution_info)

    errors_summary = []

    def _events_handler(events):
        for event in events:
            output = create_event_message_prefix(event)
            if output:
                logger.info(output)

    def _tracker_thread():
        while True:
            try:
                tenant_name, execution = executions_queue.get_nowait()
            except queue.Empty:
                break

            try:
                tenant_client = env.get_rest_client(tenant_name=tenant_name)
                execution = wait_for_execution(
                    tenant_client, execution, events_handler=_events_handler,
                    include_logs=True, timeout=None)

                if execution.error:
                    message = "Execution of workflow '{0}' for " \
                              "deployment '{1}' failed. [error={2}]".format(
                                  workflow_id, execution.deployment_id,
                                  execution.error)
                    logger.error(message)
                    errors_summary.append(message)
                else:
                    logger.info("Finished executing workflow "
                                "'{0}' on deployment"
                                " '{1}'".format(workflow_id,
                                                execution.deployment_id))
            except Exception as ex:
                # Log to the logger with a full traceback.
                # Add to errors summary with only the exception message,
                # to avoid clutter.
                logger.exception("Failed waiting for execution {0} to "
                                 "finish".format(execution.id))

                errors_summary.append(
                    "Failed waiting for execution {0} to finish; error "
                    "message: %s" % str(ex)
                )

    threads = []
    for i in range(MAX_TRACKER_THREADS):
        thread = threading.Thread(target=_tracker_thread)
        threads.append(thread)
        thread.daemon = True
        thread.start()

    while True:
        if all(not thread.is_alive() for thread in threads):
            break
        time.sleep(WAIT_FOR_EXECUTION_SLEEP_INTERVAL)

    # No need to join any thread, because if we get to this point,
    # all threads have already ended (see loop above).

    if errors_summary:
        raise CloudifyCliError("At least one execution ended with an error:\n"
                               "{0}".format('\n'.join(errors_summary)))


@agents.command(name='validate',
                short_help='Validates the connection between the'
                           ' Cloudify Manager and the live Cloudify Agents'
                           ' (installed on remote hosts). [manager only]')
@cfy.options.common_options
@cfy.options.agent_filters
@cfy.options.tenant_name(required=False,
                         mutually_exclusive_with=['all_tenants'],
                         resource_name_for_help='relevant deployment(s)')
@cfy.options.all_tenants
@cfy.options.agents_wait
@cfy.pass_logger
@cfy.pass_client()
def validate(agent_filters,
             tenant_name,
             logger,
             client,
             all_tenants,
             wait):
    """Validates the connection between the Cloudify Manager and the
    live Cloudify Agents (installed on remote hosts).
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    get_deployments_and_run_workers(
        client, agent_filters, all_tenants,
        logger, 'validate_agents', wait, None)


def _validate_certificate_file(certificate):
    if not os.path.exists(certificate):
        raise IOError("Manager's SSL certificate file does not exist in the"
                      " following path: {0}".format(certificate))
    try:
        with open(certificate, 'r') as ssl_file:
            manager_certificate = ssl_file.read()
    except IOError as e:
        raise IOError("Could not read Manager's SSL certificate from the given"
                      " path: {0}\nError:{1}".format(certificate, e))
    return manager_certificate
