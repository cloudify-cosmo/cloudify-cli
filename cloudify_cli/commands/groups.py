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

import json

from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_cli import utils
from cloudify_cli.cli import cfy
from cloudify_cli.exceptions import CloudifyCliError


@cfy.group(name='groups')
@cfy.options.common_options
@cfy.assert_manager_active()
def groups():
    """Handle deployment groups
    """
    pass


@groups.command(name='list',
                short_help='List groups for a deployment [manager only]')
@cfy.options.deployment_id(required=True)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='deployment')
@cfy.pass_client()
@cfy.pass_logger
def list(deployment_id, logger, client, tenant_name):
    """List all groups for a deployment
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info("Listing groups for deployment {0}...".format(
        deployment_id))
    try:
        deployment = client.deployments.get(deployment_id)
    except CloudifyClientError as e:
        if e.status_code != 404:
            raise
        raise CloudifyCliError('Deployment {0} not found'.format(
            deployment_id))

    groups = deployment.get('groups', {})
    scaling_groups = deployment.get('scaling_groups', {})

    if not groups:
        logger.info('No groups defined for deployment {0}'.format(
            deployment.id))
    else:
        logger.info("Groups: {0}".format(deployment.id))
        for group_name, group in sorted(groups.items()):
            logger.info('  - Name: {0}'.format(group_name))
            logger.info('    Members: {0}'.format(
                json.dumps(group['members'])))
            group_policies = group.get('policies')
            scaling_group = scaling_groups.get(group_name)
            if group_policies or scaling_group:
                logger.info('    Policies:')
                if scaling_group:
                    logger.info('      - cloudify.policies.scaling')
                if group_policies:
                    for group_policy in group_policies.values():
                        logger.info('      - {0}'.format(group_policy['type']))
            logger.info('')
