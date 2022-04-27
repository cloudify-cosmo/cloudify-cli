########
# Copyright (c) 2021 Cloudify.co Ltd. All rights reserved
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

import os
import shutil
from datetime import datetime
from contextlib import contextmanager

from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_cli.blueprint import get_blueprint_path_and_id
from cloudify_cli.cli import cfy, helptexts
from cloudify_cli.constants import DEFAULT_BLUEPRINT_PATH
from cloudify_cli.commands import blueprints, install, deployments


@cfy.command(name='apply',
             short_help='Install a blueprint or update an existing deployment '
                        'with a new blueprint [manager only]')
@cfy.options.blueprint_path(exists=False,
                            extra_message=' can be a: '
                                          '- local blueprint yaml file '
                                          '- blueprint archive '
                                          '- url to a blueprint archive '
                                          '- github repo '
                                          '(`organization/blueprint_repo'
                                          '[:tag/branch]`)')
@cfy.options.deployment_id(validate=True)
@cfy.options.blueprint_filename()
@cfy.options.blueprint_id()
@cfy.options.inputs
@cfy.options.reinstall_list
@cfy.options.workflow_id()
@cfy.options.skip_install
@cfy.options.skip_uninstall
@cfy.options.dont_skip_reinstall
@cfy.options.ignore_failure
@cfy.options.install_first
@cfy.options.preview
@cfy.options.dont_update_plugins
@cfy.options.force(help=helptexts.FORCE_UPDATE)
@cfy.options.tenant_name(required=False,
                         resource_name_for_help='blueprint and deployment')
@cfy.options.visibility(mutually_exclusive_required=False)
@cfy.options.validate
@cfy.options.include_logs
@cfy.options.json_output
@cfy.options.common_options
@cfy.options.runtime_only_evaluation
@cfy.options.auto_correct_types
@cfy.options.reevaluate_active_statuses()
# From install command
@cfy.options.skip_plugins_validation
@cfy.options.parameters
@cfy.options.allow_custom_parameters
@cfy.options.blueprint_labels
@cfy.options.deployment_labels
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.pass_context
def apply(ctx,
          blueprint_path,
          deployment_id,
          blueprint_filename,
          blueprint_id,
          inputs,
          reinstall_list,
          workflow_id,
          skip_install,
          skip_uninstall,
          dont_skip_reinstall,
          ignore_failure,
          install_first,
          preview,
          dont_update_plugins,
          force,
          tenant_name,
          visibility,
          validate,
          include_logs,
          json_output,
          runtime_only_evaluation,
          auto_correct_types,
          reevaluate_active_statuses,
          skip_plugins_validation,
          parameters,
          allow_custom_parameters,
          blueprint_labels,
          deployment_labels,
          logger,
          client
          ):
    """The `cfy apply` command uses the `cfy install` or `cfy deployments
    update` depending on the existence of the deployment specified by
    `DEPLOYMENT_ID`.

    If the deployment exists, the deployment will be updated with the given
    blueprint. Otherwise, the blueprint will be installed, and the deployment
    name will be `DEPLOYMENT_ID`.
    In both cases, the blueprint is being uploaded to the manager.

    `BLUEPRINT_PATH` can be a:

    - local blueprint yaml file.

    - blueprint archive.

    - URL to a blueprint archive.

    - GitHub repo (`organization/blueprint_repo[:tag/branch]`).

    Supported archive types are zip, tar, tar.gz, and tar.bz2

    `DEPLOYMENT_ID` is the deployment's id to install/update.

    Default values:

    If `BLUEPRINT_PATH` is not provided, the default blueprint path is
    'blueprint.yaml' in the current working directory.

    If DEPLOYMENT_ID is not provided, it will be inferred from the
    `BLUEPRINT_PATH` in one of the following ways:

    - If `BLUEPRINT_PATH` is a local file path, then `DEPLOYMENT_ID` will be
    the name of the blueprint directory.

    - If `BLUEPRINT_PATH` is an archive and --blueprint-filename/-n option is
    not provided, then `DEPLOYMENT_ID` will be the name of the blueprint
    directory.

    - If `BLUEPRINT_PATH` is an archive and --blueprint-filename/-n option is
     provided, then `DEPLOYMENT_ID` will be
     <blueprint directory name>.<blueprint_filename>.
    """
    if not blueprint_path:
        blueprint_path = blueprint_path or os.path.join(os.getcwd(),
                                                        DEFAULT_BLUEPRINT_PATH)
        logger.info("No blueprint path provided, using default: %s",
                    blueprint_path)

    with process_blueprint_and_infer_deployment_id(blueprint_path,
                                                   blueprint_filename,
                                                   blueprint_id,
                                                   deployment_id) as \
            processed_inputs:
        logger.debug("processed_inputs %s", processed_inputs)
        try:
            logger.info("Trying to find deployment %s",
                        processed_inputs['deployment_id'])
            deployment = client.deployments.get(
                deployment_id=processed_inputs['deployment_id'])
        except CloudifyClientError as e:
            if e.status_code == 404:
                deployment = None
            else:
                raise

        if not deployment:
            logger.info("Deployment %s was not found. Installing "
                        "the blueprint.", processed_inputs['deployment_id'])
            ctx.invoke(
                install.manager,
                blueprint_path=processed_inputs['processed_blueprint_path'],
                blueprint_id=processed_inputs['processed_blueprint_id'],
                validate=validate,
                deployment_id=processed_inputs['deployment_id'],
                inputs=inputs,
                workflow_id=workflow_id,
                force=force,
                visibility=visibility,
                tenant_name=tenant_name,
                skip_plugins_validation=skip_plugins_validation,
                parameters=parameters,
                allow_custom_parameters=allow_custom_parameters,
                include_logs=include_logs,
                json_output=json_output,
                blueprint_labels=blueprint_labels,
                deployment_labels=deployment_labels
            )
        else:
            # Blueprint upload and deployment update
            logger.info("Deployment %s found, updating deployment.",
                        processed_inputs['deployment_id'])
            update_bp_name = blueprint_id or processed_inputs[
                'deployment_id'] + '-' + datetime.now(
            ).strftime("%d-%m-%Y-%H-%M-%S")

            ctx.invoke(
                blueprints.upload,
                blueprint_path=processed_inputs['processed_blueprint_path'],
                blueprint_id=update_bp_name,
                validate=validate,
                visibility=visibility,
                tenant_name=tenant_name,
                labels=blueprint_labels
            )

            ctx.invoke(deployments.manager_update,
                       deployment_id=processed_inputs['deployment_id'],
                       blueprint_path=None,
                       inputs=inputs,
                       reinstall_list=reinstall_list,
                       skip_install=skip_install,
                       skip_uninstall=skip_uninstall,
                       skip_reinstall=not dont_skip_reinstall,
                       ignore_failure=ignore_failure,
                       install_first=install_first,
                       preview=preview,
                       dont_update_plugins=dont_update_plugins,
                       workflow_id=workflow_id,
                       force=force,
                       include_logs=include_logs,
                       json_output=json_output,
                       tenant_name=tenant_name,
                       blueprint_id=update_bp_name,
                       visibility=visibility,
                       validate=validate,
                       runtime_only_evaluation=runtime_only_evaluation,
                       auto_correct_types=auto_correct_types,
                       reevaluate_active_statuses=reevaluate_active_statuses
                       )

            if deployment_labels:
                ctx.invoke(deployments.add_deployment_labels,
                           labels_list=deployment_labels,
                           deployment_id=processed_inputs['deployment_id'],
                           tenant_name=tenant_name)


@contextmanager
def process_blueprint_and_infer_deployment_id(blueprint_path,
                                              blueprint_filename,
                                              blueprint_id,
                                              deployment_id):
    """
    Handle blueprint download and infer blueprint path and deployment id.
    """
    processed_blueprint_path, processed_blueprint_id = \
        get_blueprint_path_and_id(
            blueprint_path,
            blueprint_filename,
            blueprint_id
        )
    deployment_id = deployment_id or processed_blueprint_id
    try:
        yield {'processed_blueprint_path': processed_blueprint_path,
               'processed_blueprint_id': processed_blueprint_id,
               'deployment_id': deployment_id}
    finally:
        if processed_blueprint_path != blueprint_path:
            temp_directory = os.path.dirname(
                os.path.dirname(processed_blueprint_path)
            )
            shutil.rmtree(temp_directory)
