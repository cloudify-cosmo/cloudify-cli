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

from ..cli import cfy
from ..exceptions import CloudifyCliError
from .. import env
from ..table import print_data


_NODE_INSTANCE_STATE_STARTED = 'started'
AGENT_COLUMNS = ['id', 'ip', 'deployment', 'node', 'system', 'version',
                 'install_method']


def _handle_deployment_id(logger, deployment, agent_filters):
    # Handle the case when a deployment ID is provided as a positional
    # argument.
    if deployment:
        logger.warning('Passing the deployment ID as an argument is '
                       'deprecated, use --deployment-id instead')
        if agent_filters[cfy.AGENT_FILTER_DEPLOYMENT_ID]:
            raise CloudifyCliError(
                "'--deployment-id' must not be specified if a deployment ID "
                "is provided as a positional argument")
        agent_filters[cfy.AGENT_FILTER_DEPLOYMENT_ID] = [deployment]


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
@cfy.options.agent_filters
@cfy.pass_logger
@cfy.pass_client()
def agents_list(agent_filters, client, logger):
    agents = client.agents.list(**agent_filters)
    logger.info('Listing agents...')
    print_data(AGENT_COLUMNS, agents, 'Agents:')


@agents.command(name='install',
                short_help='Install deployment agents [manager only]')
@cfy.argument('deployment', required=False)
@cfy.options.common_options
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='relevant deployment(s)')
@cfy.options.all_tenants
@cfy.options.stop_old_agent
@cfy.options.manager_ip
@cfy.options.manager_certificate
@cfy.options.agent_filters
@cfy.pass_logger
@cfy.pass_client()
def install(deployment,
            agent_filters,
            tenant_name,
            logger,
            client,
            all_tenants,
            stop_old_agent,
            manager_ip,
            manager_certificate):
    """Install agents on the hosts of existing deployments

    `DEPLOYMENT` - The ID of the deployment you would like to
    install agents for.

    See Cloudify's documentation at http://docs.getcloudify.org for more
    information.
    """
    _handle_deployment_id(logger, deployment, agent_filters)
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
    get_deployments_and_run_workers(
        client, agent_filters, all_tenants,
        logger, 'install_new_agents', params)


def get_node_instances_map(
        client,
        agent_filters,
        all_tenants):
    def _get_node_instances(**kwargs):
        return client.node_instances.list(
            _include=['tenant_name', 'node_id', 'deployment_id'],
            _get_all_results=True, **kwargs)

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
    # tenant1 |- nodeinstance_1
    #         |- nodeinstance_2
    #         |- nodeinstance_3
    # tenant2 |- nodeinstance_4
    #
    # It is possible that one of the keys in the dict is 'None',
    # and that means - the current tenant.

    if agent_filters[cfy.AGENT_FILTER_NODE_INSTANCE_IDS] and (
            agent_filters[cfy.AGENT_FILTER_DEPLOYMENT_ID] or
            agent_filters[cfy.AGENT_FILTER_NODE_IDS]):
        raise CloudifyCliError(
            "If node instance ID's are provided, neither deployment ID's nor "
            "deployment ID's are allowed.")
    tenants_to_node_instances = dict()

    def _add_to_tenant_nodeinstances(node_instances):
        for node_instance in node_instances:
            tenant_node_instances = tenants_to_node_instances.setdefault(
                node_instance['tenant_name'], list())
            tenant_node_instances.append(node_instance)

    if agent_filters[cfy.AGENT_FILTER_NODE_INSTANCE_IDS]:
        candidate_ids = agent_filters[
            cfy.AGENT_FILTER_NODE_INSTANCE_IDS]
        candidates = _get_node_instances(
            ids=candidate_ids, _all_tenants=True)
        # Ensure that all requested node instance ID's actually exist.
        missing = {node_instance.id for node_instance
                   in candidates} - set(candidate_ids)
        if missing:
            raise CloudifyCliError("Node instances do not exist: "
                                   "%s" % str(missing))
        _add_to_tenant_nodeinstances(candidates)
    else:
        # If at least one deployment ID was provided, then ensure
        # all specified deployment ID's indeed exist.
        if agent_filters[cfy.AGENT_FILTER_DEPLOYMENT_ID]:
            existing_deployments = client.deployments.list(
                id=agent_filters[cfy.AGENT_FILTER_DEPLOYMENT_ID],
                _include=['id'])
            missing = {deployment.id for deployment in existing_deployments} \
                - set(agent_filters[cfy.AGENT_FILTER_DEPLOYMENT_ID])
            if missing:
                raise CloudifyCliError("Deployments do not exist: "
                                       "%s" % str(missing))
        ni_filters = dict()
        if agent_filters[cfy.AGENT_FILTER_NODE_IDS]:
            ni_filters['node_id'] = agent_filters[
                cfy.AGENT_FILTER_NODE_IDS]
        if agent_filters[cfy.AGENT_FILTER_DEPLOYMENT_ID]:
            ni_filters['deployment_id'] = agent_filters[
                cfy.AGENT_FILTER_DEPLOYMENT_ID]
        candidates = _get_node_instances(_all_tenants=all_tenants,
                                         **ni_filters)
        _add_to_tenant_nodeinstances(candidates)

    # Remove empty tenants.
    for tenant_name, node_instances in tenants_to_node_instances.items():
        if not node_instances:
            del tenants_to_node_instances[tenant_name]

    return tenants_to_node_instances


def get_deployments_and_run_workers(
        client,
        agent_filters,
        all_tenants,
        logger,
        workflow_id,
        parameters=None):
    tenants_to_ni_cache = get_node_instances_map(
        client, agent_filters, all_tenants)

    if not tenants_to_ni_cache:
        raise CloudifyCliError("No eligible deployments found")

    for tenant_name, node_instances in tenants_to_ni_cache.items():
        tenant_client = env.get_rest_client(tenant_name=tenant_name)
        # Group node instances by deployment ID's.
        deployments_map = dict()
        for node_instance in node_instances:
            dep_instances = deployments_map.setdefault(
                node_instance.deployment_id, list())
            dep_instances.append(node_instance)

        for deployment_id, dep_node_instances in deployments_map.items():
            execution_params = {
                'node_instance_ids': [ni.id for ni in dep_node_instances],
            }
            if agent_filters[cfy.AGENT_FILTER_INSTALL_METHODS]:
                execution_params['install_methods'] = agent_filters[
                    cfy.AGENT_FILTER_INSTALL_METHODS]
            if parameters:
                execution_params.update(parameters)
            execution = tenant_client.executions.start(
                deployment_id, workflow_id, execution_params,
                allow_custom_parameters=True)
            logger.info(
                "Started execution for deployment '%s': %s",
                deployment_id, execution.id
            )

    logger.info("Executions started for all applicable deployments."
                "You may now use the 'cfy events list' command to "
                "view the events associated with these executions.")


@agents.command(name='validate',
                short_help='Validates the connection between the'
                           ' Cloudify Manager and the live Cloudify Agents'
                           ' (installed on remote hosts). [manager only]')
@cfy.argument('deployment', required=False)
@cfy.options.common_options
@cfy.options.agent_filters
@cfy.options.tenant_name_for_list(
    required=False, resource_name_for_help='relevant deployment(s)')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def validate(deployment,
             agent_filters,
             tenant_name,
             logger,
             client,
             all_tenants):
    """Validates the connection between the Cloudify Manager and the
    live Cloudify Agents (installed on remote hosts).

        `DEPLOYMENT_ID` - The ID of the deployment you would like to
        validate agents for.
    """

    _handle_deployment_id(logger, deployment, agent_filters)
    get_deployments_and_run_workers(
        client, agent_filters, all_tenants,
        logger, 'validate_agents')


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
