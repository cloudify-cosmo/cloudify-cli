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

from cloudify_cli import env
from cloudify_cli.cli import cfy
from cloudify_cli.table import print_data

SECRET_PROVIDER_COLUMNS = [
    'name',
    'type',
    'connection_parameters',
    'visibility',
    'tenant_name',
    'created_by',
    'created_at',
]


@cfy.group(name='secret_provider')
@cfy.options.common_options
def secret_provider():
    """
    Handle Cloudify secret providers
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@secret_provider.command(
    name='create',
    short_help='Create a new secret provider',
)
@cfy.options.secret_provider_name
@cfy.options.secret_provider_type
@cfy.options.connection_parameters
@cfy.options.tenant_name(
    required=False,
    resource_name_for_help='secret_provider',
)
@cfy.options.visibility(
    mutually_exclusive_required=False,
)
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(
    use_tenant_in_header=True,
)
@cfy.pass_logger
def create(
        secret_provider_name,
        secret_provider_type,
        connection_parameters,
        tenant_name,
        visibility,
        logger,
        client,
):
    client.secret_provider.create(
        secret_provider_name,
        secret_provider_type,
        connection_parameters,
        tenant_name,
        visibility,
    )

    logger.info(
        'Secret provider `{0}` created'.format(
            secret_provider_name,
        ),
    )


@secret_provider.command(
    name='list',
    short_help="List all secret providers",
)
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
@cfy.options.common_options
def list(
        logger,
        client,
):
    logger.info('Listing all secret providers...')
    secrets_list = client.secret_provider.list()
    print_data(SECRET_PROVIDER_COLUMNS, secrets_list, 'Secret providers:')
    total = secrets_list.metadata.pagination.total
    logger.info(
        'Showing {0} of {1} secret providers'.format(
            len(secrets_list),
            total,
        ),
    )
