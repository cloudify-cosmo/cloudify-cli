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
import time

from StringIO import StringIO
from cloudify_cli import utils
from cloudify_cli.execution_events_fetcher import wait_for_execution
from cloudify_cli.logger import lgr
from cloudify_cli.logger import get_events_logger
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.exceptions import ExecutionTimeoutError
from cloudify_cli.exceptions import SuppressedCloudifyCliError
from cloudify_rest_client.exceptions import MissingRequiredDeploymentInputError
from cloudify_rest_client.exceptions import UnknownDeploymentInputError
from cloudify_rest_client.exceptions import DeploymentEnvironmentCreationInProgressError


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


def list(blueprint_id):
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)
    if blueprint_id:
        lgr.info("Getting deployments list for blueprint: '{0}'... [manager={1}]"
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


def execute(workflow, deployment_id, timeout, force, allow_custom_parameters, include_logs, parameters):
    management_ip = utils.get_management_server_ip()
    lgr.info("Executing workflow '{0}' on deployment '{1}' at"
             " management server {2} [timeout={3} seconds]"
             .format(workflow,
                     deployment_id,
                     management_ip,
                     timeout))

    events_logger = get_events_logger()

    events_message = "* Run 'cfy events --include-logs " \
                     "--execution-id {0}' for retrieving the " \
                     "execution's events/logs"
    try:
        client = utils.get_rest_client(management_ip)
        try:
            execution = client.deployments.execute(
                deployment_id,
                workflow,
                parameters=parameters,
                allow_custom_parameters=allow_custom_parameters,
                force=force)
        except DeploymentEnvironmentCreationInProgressError:
            # wait for deployment environment creation workflow to end
            lgr.info('Deployment environment creation is in progress!')
            lgr.info('Waiting for create_deployment_environment '
                     'workflow execution to finish...')
            now = time.time()
            wait_for_execution(client,
                               deployment_id,
                               get_deployment_environment_creation_execution(
                                   client, deployment_id),
                               events_handler=events_logger,
                               include_logs=include_logs,
                               timeout=timeout)
            remaining_timeout = time.time() - now
            timeout -= remaining_timeout
            # try to execute user specified workflow
            execution = client.deployments.execute(
                deployment_id,
                workflow,
                parameters=parameters,
                allow_custom_parameters=allow_custom_parameters,
                force=force)

        execution = wait_for_execution(client,
                                       deployment_id,
                                       execution,
                                       events_handler=events_logger,
                                       include_logs=include_logs,
                                       timeout=timeout)
        if execution.error:
            lgr.info("Execution of workflow '{0}' for deployment "
                     "'{1}' failed. [error={2}]"
                     .format(workflow,
                             deployment_id,
                             execution.error))
            lgr.info(events_message.format(execution.id))
            raise SuppressedCloudifyCliError()
        else:
            lgr.info("Finished executing workflow '{0}' on deployment"
                     "'{1}'".format(workflow, deployment_id))
            lgr.info(events_message.format(execution.id))
    except ExecutionTimeoutError, e:
        lgr.info("Execution of workflow '{0}' for deployment '{1}' timed out. "
                 "* Run 'cfy executions cancel --execution-id {2}' to cancel"
                 " the running workflow.".format(workflow,
                                                 deployment_id,
                                                 e.execution_id))
        lgr.info(events_message.format(e.execution_id))
        raise SuppressedCloudifyCliError()


def outputs(deployment_id):

    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)

    lgr.info("Getting outputs for deployment: {0} [manager={1}]".format(
        deployment_id, management_ip))

    response = client.deployments.outputs.get(deployment_id)
    outputs_ = StringIO()
    for output_name, output in response.outputs.iteritems():
        outputs_.write('\t{0}:{1}'.format(output_name, os.linesep))
        for k, v in output.iteritems():
            outputs_.write('\t\t{0}: {1}{2}'.format(k, v, os.linesep))
    outputs_.write(os.linesep)
    lgr.info(outputs_.getvalue())


def get_deployment_environment_creation_execution(client, deployment_id):
    executions = client.deployments.list_executions(deployment_id)
    for e in executions:
        if e.workflow_id == 'create_deployment_environment':
            return e
    raise RuntimeError('Failed to get create_deployment_environment workflow execution'
                       '. Available executions: {0}'.format(executions))