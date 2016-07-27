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
# * See the License for the specific language governing permissions and
#    * limitations under the License.

from cloudify_rest_client.exceptions import CloudifyClientError

from .. import utils
from .. import common
from ..config import cfy
from ..exceptions import CloudifyCliError


@cfy.group(name='workflows')
@cfy.assert_manager_active
def workflows():
    """Handle deployment workflows
    """


@workflows.command(name='get')
@cfy.argument('workflow-id')
@cfy.options.deployment_id(required=True)
@cfy.options.verbose
@cfy.add_logger
@cfy.add_client()
def get(workflow_id, deployment_id, logger, client):
    """Retrieve information for a specific workflow of a specific deployment

    `WORKFLOW_ID` is the id of the workflow to get information on.
    """
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

    columns = ['blueprint_id', 'deployment_id', 'name', 'created_at']
    defaults = {
        'blueprint_id': deployment.blueprint_id,
        'deployment_id': deployment.id
    }
    pt = utils.table(columns, data=[workflow], defaults=defaults)

    common.print_table('Workflows:', pt)

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


@workflows.command(name='list')
@cfy.options.deployment_id(required=True)
@cfy.options.verbose
@cfy.add_logger
@cfy.add_client()
def list(deployment_id, logger, client):
    """List all workflows on the manager

    `DEPLOYMENT_ID` is the id of the deployment to list workflows for.
    """
    logger.info('Listing workflows for deployment {0}...'.format(
        deployment_id))
    deployment = client.deployments.get(deployment_id)
    sorted_workflows = sorted(deployment.workflows, key=lambda w: w.name)

    columns = ['blueprint_id', 'deployment_id', 'name', 'created_at']
    defaults = {
        'blueprint_id': deployment.blueprint_id,
        'deployment_id': deployment.id
    }
    pt = utils.table(columns, data=sorted_workflows, defaults=defaults)
    common.print_table('Workflows:', pt)
