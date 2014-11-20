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
Handles all commands that start with 'cfy deployments'
"""

import os
from StringIO import StringIO

from cloudify_rest_client.exceptions import MissingRequiredDeploymentInputError
from cloudify_rest_client.exceptions import UnknownDeploymentInputError
from cloudify_cli import utils
from cloudify_cli.logger import get_logger
from cloudify_cli.exceptions import SuppressedCloudifyCliError


def _print_deployment_inputs(client, blueprint_id):
    logger = get_logger()
    blueprint = client.blueprints.get(blueprint_id)
    logger.info('Deployment inputs:')
    inputs_output = StringIO()
    for input_name, input_def in blueprint.plan['inputs'].iteritems():
        inputs_output.write('\t{0}:{1}'.format(input_name, os.linesep))
        for k, v in input_def.iteritems():
            inputs_output.write('\t\t{0}: {1}{2}'.format(k, v, os.linesep))
    inputs_output.write(os.linesep)
    logger.info(inputs_output.getvalue())


def ls(blueprint_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)
    if blueprint_id:
        logger.info("Getting deployments list for blueprint: "
                    "'{0}'... [manager={1}]"
                    .format(blueprint_id, management_ip))
    else:
        logger.info('Getting deployments list...[manager={0}]'
                    .format(management_ip))
    deployments = client.deployments.list()
    if blueprint_id:
        deployments = filter(lambda deployment:
                             deployment['blueprint_id'] == blueprint_id,
                             deployments)

    pt = utils.table(
        ['id',
         'blueprint_id',
         'created_at',
         'updated_at'],
        deployments)
    utils.print_table('Deployments:', pt)


def create(blueprint_id, deployment_id, inputs):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    inputs = utils.json_to_dict(inputs, 'inputs')

    logger.info('Creating new deployment from blueprint {0} at '
                'management server {1}'
                .format(blueprint_id, management_ip))
    client = utils.get_rest_client(management_ip)

    try:
        deployment = client.deployments.create(blueprint_id,
                                               deployment_id,
                                               inputs=inputs)
    except MissingRequiredDeploymentInputError, e:
        logger.info('Unable to create deployment, not all '
                    'required inputs have been specified...')
        _print_deployment_inputs(client, blueprint_id)
        raise SuppressedCloudifyCliError(str(e))
    except UnknownDeploymentInputError, e:
        logger.info(
            'Unable to create deployment, an unknown input was specified...')
        _print_deployment_inputs(client, blueprint_id)
        raise SuppressedCloudifyCliError(str(e))

    logger.info("Deployment created, deployment's id is: {0}"
                .format(deployment.id))


def delete(deployment_id, ignore_live_nodes):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info('Deleting deployment {0} from management server {1}'
                .format(deployment_id, management_ip))
    client = utils.get_rest_client(management_ip)
    client.deployments.delete(deployment_id, ignore_live_nodes)
    logger.info("Deleted deployment successfully")


def outputs(deployment_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    logger.info("Getting outputs for deployment: {0} [manager={1}]".format(
        deployment_id, management_ip))

    dep = client.deployments.get(deployment_id, _include=['outputs'])
    outputs_def = dep.outputs
    response = client.deployments.outputs.get(deployment_id)
    outputs_ = StringIO()
    for output_name, output in response.outputs.iteritems():
        outputs_.write(' - "{0}":{1}'.format(output_name, os.linesep))
        description = outputs_def[output_name].get('description', '')
        outputs_.write('     Description: {0}{1}'.format(description,
                                                         os.linesep))
        outputs_.write('     Value: {0}{1}'.format(output, os.linesep))
    logger.info(outputs_.getvalue())
