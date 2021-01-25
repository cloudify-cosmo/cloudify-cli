from .. import env
from .. import utils
from ..cli import cfy
from ..table import print_data, print_details
from ..utils import validate_visibility, handle_client_error

FILTERS_COLUMNS = ['id', 'filter_rules', 'created_at', 'updated_at',
                   'visibility', 'tenant_name', 'created_by']

NOT_FOUND_MSG = 'Requested filter with ID `{0}` was not found in this tenant'


@cfy.group(name='filters')
@cfy.options.common_options
def filters():
    """Handle filters"""
    if not env.is_initialized():
        env.raise_uninitialized()


@filters.command(name='create', short_help='Create a new filter')
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.argument('filter-rules',
              callback=cfy.parse_and_validate_filter_rules_list)
@cfy.options.visibility(mutually_exclusive_required=False)
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def create(filter_id,
           filter_rules,
           visibility,
           tenant_name,
           logger,
           client):
    """Create a new filter

    `FILTER-ID` is the new filter's ID

    `FILTER-RULES` are a list of filter rules separated with "and".
    Filter rules must be one of: <key>=<value>, <key>=[<value1>,<value2>,...],
    <key>!=<value>, <key>!=[<value1>,<value2>,...], <key> is null,
    <key> is not null. E.g. "a=b and c!=[d,e] and f is not null".
    The filter rules will be saved in lower case.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)

    new_filter = client.filters.create(filter_id, filter_rules, visibility)
    logger.info('Filter `{0}` created'.format(new_filter.id))


@filters.command(name='get', short_help='Get details for a single filter')
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def get(filter_id, tenant_name, logger, client):
    """Get details for a single filter

    `FILTER-ID` is the filter's ID
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = NOT_FOUND_MSG.format(filter_id)
    with handle_client_error(404, graceful_msg, logger):
        logger.info('Getting info for filter `{0}`...'.format(filter_id))
        filter_details = client.filters.get(filter_id)
        _modify_filter_details(filter_details)
        print_details(filter_details, 'Requested filter info:')


@filters.command(name='list', short_help="List all filters")
@cfy.options.sort_by('id')
@cfy.options.descending
@cfy.options.common_options
@cfy.options.tenant_name_for_list(required=False,
                                  resource_name_for_help='filter')
@cfy.options.all_tenants
@cfy.options.search
@cfy.options.pagination_offset
@cfy.options.pagination_size
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def filters_list(sort_by,
                 descending,
                 tenant_name,
                 all_tenants,
                 search,
                 pagination_offset,
                 pagination_size,
                 logger,
                 client):
    """List all Filters
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing all filters...')
    filters_list_res = client.filters.list(
        sort=sort_by,
        is_descending=descending,
        _all_tenants=all_tenants,
        _search=search,
        _offset=pagination_offset,
        _size=pagination_size
    )
    for filter_elem in filters_list_res:
        _modify_filter_details(filter_elem)
    print_data(FILTERS_COLUMNS, filters_list_res, 'Filters:')
    total = filters_list_res.metadata.pagination.total
    logger.info('Showing {0} of {1} filters'.format(
        len(filters_list_res), total))


def _modify_filter_details(filter_details):
    filter_details.pop('value')
    filter_details['filter_rules'] = '\"{0}\"'.format(
        ' and '.join(filter_details.get('labels_filters', [])))
    filter_details.pop('labels_filters')


@filters.command(name='update', short_help='Update an existing filter')
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.update_visibility
@cfy.options.update_filter_rules
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client(use_tenant_in_header=True)
@cfy.pass_logger
def update(filter_id,
           visibility,
           filter_rules,
           tenant_name,
           logger,
           client):
    """Update an existing filter's filter rules or visibility

    `FILTER-ID` is the filter's ID
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)
    graceful_msg = NOT_FOUND_MSG.format(filter_id)
    with handle_client_error(404, graceful_msg, logger):
        new_filter = client.filters.update(filter_id, filter_rules, visibility)
        logger.info('Filter `{0}` updated'.format(new_filter.id))


@filters.command(name='delete', short_help='Delete a filter')
@cfy.argument('filter-id', callback=cfy.validate_name)
@cfy.options.tenant_name(required=False, resource_name_for_help='filter')
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def delete(filter_id, tenant_name, logger, client):
    """Delete a filter

    `FILTER-ID` is the filter's ID
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = NOT_FOUND_MSG.format(filter_id)
    with handle_client_error(404, graceful_msg, logger):
        logger.info('Deleting filter `{0}`...'.format(filter_id))
        client.filters.delete(filter_id)
        logger.info('Filter removed')
