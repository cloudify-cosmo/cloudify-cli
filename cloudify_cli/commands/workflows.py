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

import click
from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_cli import utils
from cloudify_cli.cli import cfy
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.logger import get_global_json_output
from cloudify_cli.table import print_data, print_single

WORKFLOW_COLUMNS = ['blueprint_id', 'deployment_id', 'name',
                    'availability_rules']


@cfy.group(name='workflows')
@cfy.assert_manager_active()
def workflows():
    """Handle deployment workflows
    """
    pass


@workflows.command(name='get',
                   short_help='Retrieve workflow information [manager only]')
@cfy.argument('workflow-id')
@cfy.options.deployment_id(required=True)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.pass_logger
@cfy.pass_client()
@cfy.options.extended_view
def get(workflow_id, deployment_id, logger, client, tenant_name):
    """Retrieve information for a specific workflow of a specific deployment

    `WORKFLOW_ID` is the id of the workflow to get information on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    try:
        logger.info('Retrieving workflow {0} for deployment {1}'.format(
            workflow_id, deployment_id))
        deployment = client.deployments.get(deployment_id)
        workflow = next((wf for wf in deployment.workflows if
                         wf.name == workflow_id), None)
        if not workflow:
            raise CloudifyCliError(
                'Workflow {0} of deployment {1} not found'
                .format(workflow_id, deployment_id))
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} not found'.format(
            deployment_id))

    defaults = {
        'blueprint_id': deployment.blueprint_id,
        'deployment_id': deployment.id
    }
    columns = WORKFLOW_COLUMNS

    if get_global_json_output():
        columns += ['parameters']
    print_single(columns, workflow, 'Workflows:', defaults=defaults)

    if not get_global_json_output():
        # print workflow parameters
        mandatory_params = dict()
        optional_params = dict()
        for param_name, param in workflow.parameters.items():
            params_group = optional_params if 'default' in param else \
                mandatory_params
            params_group[param_name] = param

        logger.info('Workflow Parameters:')
        logger.info('\tMandatory Parameters:')
        for param_name, param in mandatory_params.items():
            if 'description' in param:
                logger.info('\t\t{0}\t({1})'.format(param_name,
                                                    param['description']))
            else:
                logger.info('\t\t{0}'.format(param_name))

        logger.info('\tOptional Parameters:')
        for param_name, param in optional_params.items():
            if 'description' in param:
                logger.info('\t\t{0}: \t{1}\t({2})'.format(
                    param_name, param['default'], param['description']))
            else:
                logger.info('\t\t{0}: \t{1}'.format(param_name,
                                                    param['default']))
        logger.info('')


def _format_workflow(wf):
    if wf.get('availability_rules'):
        wf['availability_rules'] = ', '.join(wf['availability_rules'].keys())
    return wf


@workflows.command(name='list',
                   short_help='List workflows for a deployment [manager only]')
@cfy.options.deployment_id(required=True)
@cfy.options.common_options
@click.option('--all', 'all_workflows', is_flag=True,
              help='Also show unavailable workflows')
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.pass_logger
@cfy.pass_client()
@cfy.options.extended_view
def list(deployment_id, all_workflows, logger, client, tenant_name):
    """List all workflows on the manager for a specific deployment
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing workflows for deployment %s...', deployment_id)
    deployment = client.deployments.get(deployment_id)

    workflows = sorted(deployment.workflows, key=lambda w: w.name)
    columns = WORKFLOW_COLUMNS
    hidden_count = 0
    if not all_workflows:
        total_count = len(workflows)
        workflows = [wf for wf in workflows if wf.is_available]
        hidden_count = total_count - len(workflows)
    else:
        columns = columns + ['is_available']

    defaults = {
        'blueprint_id': deployment.blueprint_id,
        'deployment_id': deployment.id
    }
    if not get_global_json_output():
        workflows = [_format_workflow(wf) for wf in workflows]
    print_data(columns, workflows, 'Workflows:', defaults=defaults)
    if hidden_count:
        logger.info('%d unavailable workflows hidden (use --all to show)',
                    hidden_count)
