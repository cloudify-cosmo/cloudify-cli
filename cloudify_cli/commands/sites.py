########
# Copyright (c) 2013-2019 Cloudify Technologies Ltd. All rights reserved
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


from cloudify_cli import env, utils
from cloudify_cli.cli import cfy
from cloudify_cli.table import print_data, print_single
from cloudify_cli.utils import handle_client_error, validate_visibility

SITES_COLUMNS = ['name', 'location', 'visibility', 'tenant_name',
                 'created_at', 'created_by']


@cfy.group(name='sites')
@cfy.options.common_options
def sites():
    """
    Handle Cloudify sites
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@sites.command(name='create', short_help='Create a new site')
@cfy.argument('name', callback=cfy.validate_name)
@cfy.options.location
@cfy.options.visibility(mutually_exclusive_required=False)
@cfy.options.tenant_name(required=False, resource_name_for_help='site')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def create(name, location, visibility, tenant_name, client, logger):
    """Create a new site

    `NAME` is the new site's name
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)
    client.sites.create(name, location, visibility)
    logger.info('Site `{0}` created'.format(name))


@sites.command(name='get', short_help='Get details for a single site')
@cfy.argument('name', callback=cfy.validate_name)
@cfy.options.tenant_name(required=False, resource_name_for_help='site')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
@cfy.options.extended_view
def get(name, tenant_name, client, logger):
    """Get details for a single site

    `NAME` is the site's name
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = 'Requested site with name `{0}` was not found in this ' \
                   'tenant'.format(name)
    with handle_client_error(404, graceful_msg, logger):
        logger.info('Getting info for site `{0}`...'.format(name))
        site_details = client.sites.get(name)
        print_single(SITES_COLUMNS, site_details, 'Requested site info:')


@sites.command(name='update', short_help='Update an existing site')
@cfy.argument('name', callback=cfy.validate_name)
@cfy.options.location
@cfy.options.update_visibility
@cfy.options.new_name('site')
@cfy.options.tenant_name(required=False, resource_name_for_help='site')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def update(name, location, visibility, new_name, tenant_name, client, logger):
    """Update an existing site

    `NAME` is the site's name
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)
    graceful_msg = 'Requested site with name `{0}` was not found'.format(name)
    with handle_client_error(404, graceful_msg, logger):
        client.sites.update(name, location, visibility, new_name)
        logger.info('Site `{0}` updated'.format(name))


@sites.command(name='list', short_help='List all sites')
@cfy.options.sort_by('name')
@cfy.options.descending
@cfy.options.common_options
@cfy.options.tenant_name_for_list(required=False,
                                  resource_name_for_help='site')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
@cfy.options.extended_view
def list(sort_by,
         descending,
         tenant_name,
         all_tenants,
         search,
         pagination_offset,
         pagination_size,
         client,
         logger):
    """
    List all sites
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing all sites...')
    sites_list = client.sites.list(
        sort=sort_by,
        is_descending=descending,
        _all_tenants=all_tenants,
        _search=search,
        _offset=pagination_offset,
        _size=pagination_size
    )
    print_data(SITES_COLUMNS, sites_list, 'Sites:')
    total = sites_list.metadata.pagination.total
    logger.info('Showing {0} of {1} sites'.format(len(sites_list), total))


@sites.command(name='delete', short_help='Delete a site')
@cfy.argument('name', callback=cfy.validate_name)
@cfy.options.tenant_name(required=False, resource_name_for_help='secret')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete(name, tenant_name, client, logger):
    """Delete a site

    `NAME` is the site's name
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = 'Requested site with name `{0}` was not found'.format(name)
    with handle_client_error(404, graceful_msg, logger):
        logger.info('Deleting site `{0}`...'.format(name))
        client.sites.delete(name)
        logger.info('Site deleted')
