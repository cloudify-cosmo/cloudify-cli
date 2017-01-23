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

from cloudify_rest_client.exceptions import CloudifyClientError

from ..table import print_data
from .. import utils
from ..cli import cfy
from ..exceptions import CloudifyCliError

WORKFLOW_COLUMNS = ['blueprint_id', 'deployment_id', 'name', 'created_at']


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
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.pass_logger
@cfy.pass_client()
def get(workflow_id, deployment_id, logger, client, tenant_name):
    """Retrieve information for a specific workflow of a specific deployment

    `WORKFLOW_ID` is the id of the workflow to get information on.
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    try:
        logger.info('Retrieving workflow {0} for deployment {1}'.format(
            workflow_id, deployment_id))
        deployment = client.deployments.get(deployment_id)
        workflow = next((wf for wf in deployment.workflows if
                         wf.name == workflow_id), None)
        if not workflow:
            raise CloudifyCliError(
                'Workflow {0} not found'.format(workflow_id, deployment_id))
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} not found'.format(
            deployment_id))

    defaults = {
        'blueprint_id': deployment.blueprint_id,
        'deployment_id': deployment.id
    }
    print_data(WORKFLOW_COLUMNS, workflow, 'Workflows:', defaults=defaults)

    # print workflow parameters
    mandatory_params = dict()
    optional_params = dict()
    for param_name, param in utils.decode_dict(
            workflow.parameters).iteritems():
        params_group = optional_params if 'default' in param else \
            mandatory_params
        params_group[param_name] = param

    logger.info('Workflow Parameters:')
    logger.info('\tMandatory Parameters:')
    for param_name, param in mandatory_params.iteritems():
        if 'description' in param:
            logger.info('\t\t{0}\t({1})'.format(param_name,
                                                param['description']))
        else:
            logger.info('\t\t{0}'.format(param_name))

    logger.info('\tOptional Parameters:')
    for param_name, param in optional_params.iteritems():
        if 'description' in param:
            logger.info('\t\t{0}: \t{1}\t({2})'.format(
                param_name, param['default'], param['description']))
        else:
            logger.info('\t\t{0}: \t{1}'.format(param_name,
                                                param['default']))
    logger.info('')


@workflows.command(name='list',
                   short_help='List workflows for a deployment [manager only]')
@cfy.options.deployment_id(required=True)
@cfy.options.verbose()
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.pass_logger
@cfy.pass_client()
def list(deployment_id, logger, client, tenant_name):
    """List all workflows on the manager for a specific deployment
    """
    if tenant_name:
        logger.info('Explicitly using tenant `{0}`'.format(tenant_name))
    logger.info('Listing workflows for deployment {0}...'.format(
        deployment_id))
    deployment = client.deployments.get(deployment_id)
    workflows = sorted(deployment.workflows, key=lambda w: w.name)

    defaults = {
        'blueprint_id': deployment.blueprint_id,
        'deployment_id': deployment.id
    }
    print_data(WORKFLOW_COLUMNS, workflows, 'Workflows:', defaults=defaults)
