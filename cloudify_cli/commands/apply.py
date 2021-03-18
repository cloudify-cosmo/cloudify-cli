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

from ..cli import cfy, helptexts
from ..blueprint import get_blueprint_path_and_id
from . import blueprints, install, deployments


@cfy.command(name='apply',
             short_help='Install a blueprint or update existing deployment '
                        'with blueprint [manager only]')
@cfy.argument('blueprint-path')
@cfy.argument('deployment-id')
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
          logger,
          client
          ):
    """Apply command uses cfy install or deployment update depends on
    existence of DEPLOYMENT_ID deployment.

    If the deployment exists, the deployment will be updated with the
    given blueprint.
    otherwise the blueprint will installed (the deployment name will be
    DEPLOYMENT_ID).
    In both cases the blueprint is being uploaded to the manager.

    `BLUEPRINT_PATH` can be a:
        - local blueprint yaml file
        - blueprint archive
        - url to a blueprint archive
        - github repo (`organization/blueprint_repo[:tag/branch]`)

    Supported archive types are: zip, tar, tar.gz and tar.bz2

    `DEPLOYMENT_ID` is the deployment's id to install/update.
    """
    # check if deployment exists
    if deployment_id not in [deployment.id for deployment in
                             client.deployments.list()]:
        ctx.invoke(
            install.manager,
            blueprint_path=blueprint_path,
            blueprint_id=blueprint_id,
            blueprint_filename=blueprint_filename,
            validate=validate,
            deployment_id=deployment_id,
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
        )
    else:
        # Blueprint upload and deployment update
        logger.info("Deployment {id} found, updating deployment.".format(
            id=deployment_id))
        update_bp_name = blueprint_id or deployment_id + '-' + datetime.now(
        ).strftime("%d-%m-%Y-%H-%M-%S")
        processed_blueprint_path, blueprint_id = get_blueprint_path_and_id(
            blueprint_path,
            blueprint_filename,
            update_bp_name
        )

        try:
            ctx.invoke(
                blueprints.upload,
                blueprint_path=processed_blueprint_path,
                blueprint_id=blueprint_id,
                blueprint_filename=blueprint_filename,
                validate=validate,
                visibility=visibility,
                tenant_name=tenant_name
            )

        finally:
            # When an archive file is passed, it's extracted to a temporary
            # directory to get the blueprint file. Once the blueprint has been
            # uploaded, the temporary directory needs to be cleaned up.
            if processed_blueprint_path != blueprint_path:
                temp_directory = os.path.dirname(
                    os.path.dirname(processed_blueprint_path)
                )
                shutil.rmtree(temp_directory)

        ctx.invoke(deployments.manager_update,
                   deployment_id=deployment_id,
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
