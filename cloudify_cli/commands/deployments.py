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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

"""
Handles all commands that start with 'cfy deployments'
"""

import json
import os
from StringIO import StringIO

from cloudify_rest_client.exceptions import MissingRequiredDeploymentInputError
from cloudify_rest_client.exceptions import UnknownDeploymentInputError

from cloudify_cli import utils
from cloudify_cli.logger import lgr
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.exceptions import SuppressedCloudifyCliError


def _print_deployment_inputs(client, blueprint_id):
    blueprint = client.blueprints.get(blueprint_id)
    lgr.info('Deployment inputs:')
    inputs_output = StringIO()
    for input_name, input_def in blueprint.plan['inputs'].iteritems():
        inputs_output.write('\t{0}:{1}'.format(input_name, os.linesep))
        for k, v in input_def.iteritems():
            inputs_output.write('\t\t{0}: {1}{2}'.format(k, v, os.linesep))
    inputs_output.write(os.linesep)
    lgr.info(inputs_output.getvalue())


def ls(blueprint_id):
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)
    if blueprint_id:
        lgr.info("Getting deployments list for blueprint: "
                 "'{0}'... [manager={1}]"
                 .format(blueprint_id, management_ip))
    else:
        lgr.info('Getting deployments list...[manager={0}]'
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


def create(blueprint_id, deployment_id, inputs=None):
    management_ip = utils.get_management_server_ip()
    try:
        if inputs:
            if os.path.exists(inputs):
                with open(inputs, 'r') as f:
                    inputs = json.loads(f.read())
            else:
                inputs = json.loads(inputs)
    except ValueError, e:
        msg = "'inputs' must be a valid JSON. {}".format(str(e))
        raise CloudifyCliError(msg)

    lgr.info('Creating new deployment from blueprint {0} at '
             'management server {1}'
             .format(blueprint_id, management_ip))
    client = utils.get_rest_client(management_ip)

    try:
        deployment = client.deployments.create(blueprint_id,
                                               deployment_id,
                                               inputs=inputs)
    except MissingRequiredDeploymentInputError, e:
        lgr.info('Unable to create deployment, not all '
                 'required inputs have been specified...')
        _print_deployment_inputs(client, blueprint_id)
        raise SuppressedCloudifyCliError(str(e))
    except UnknownDeploymentInputError, e:
        lgr.info(
            'Unable to create deployment, an unknown input was specified...')
        _print_deployment_inputs(client, blueprint_id)
        raise SuppressedCloudifyCliError(str(e))

    lgr.info("Deployment created, deployment's id is: {0}"
             .format(deployment.id))


def delete(deployment_id, ignore_live_nodes):
    management_ip = utils.get_management_server_ip()
    lgr.info('Deleting deployment {0} from management server {1}'
             .format(deployment_id, management_ip))
    client = utils.get_rest_client(management_ip)
    client.deployments.delete(deployment_id, ignore_live_nodes)
    lgr.info("Deleted deployment successfully")


def outputs(deployment_id):
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    lgr.info("Getting outputs for deployment: {0} [manager={1}]".format(
        deployment_id, management_ip))

    dep = client.deployments.get(deployment_id, _include=['outputs'])
    outputs_def = dep.outputs
    response = client.deployments.outputs.get(deployment_id)
    outputs_ = StringIO()
    for output_name, output in response.outputs.iteritems():
        outputs_.write(' - "{0}":{1}'.format(output_name, os.linesep))
        description = outputs_def[output_name]['description']
        outputs_.write('     Description: {0}{1}'.format(description,
                                                         os.linesep))
        outputs_.write('     Value: {0}{1}'.format(output, os.linesep))
    lgr.info(outputs_.getvalue())
