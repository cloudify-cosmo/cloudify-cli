import re

from . import utils
from .exceptions import CloudifyCliError
from .table import print_data, print_details
from .utils import validate_visibility, handle_client_error

from cloudify_rest_client.exceptions import InvalidFilterRule


FILTERS_COLUMNS = ['id', 'labels_filter_rules', 'attrs_filter_rules',
                   'created_at', 'updated_at', 'visibility',
                   'tenant_name', 'created_by']

NOT_FOUND_MSG = 'Requested {0} filter with ID `{1}` was not found in ' \
                'this tenant'

OPERATOR_MAPPING = {
    '=': 'any_of',
    '!=': 'not_any_of',
    'contains': 'contains',
    'does-not-contain': 'not_contains',
    'starts-with': 'starts_with',
    'ends-with': 'ends_with',
    'is null': 'is_null',
    'is not null': 'is_not_null',
    'is not empty': 'is_not_empty'
}

REVERSED_OPERATOR_MAPPING = {v: k for k, v in OPERATOR_MAPPING.items()}


class BadLabelsFilterRule(CloudifyCliError):
    def __init__(self, labels_filter_value):
        super(CloudifyCliError, self).__init__(
            'The labels filter rule `{0}` is not in the right format. It must '
            'be one of: <key>=<value>, <key>!=<value>, <key> is null, '
            '<key> is not null. <value> can be a single string or a list of '
            'strings of the form [<value1>,<value2>,...]'.format(
                labels_filter_value)
        )


class BadAttributesFilterRule(CloudifyCliError):
    def __init__(self, labels_filter_value):
        super(CloudifyCliError, self).__init__(
            'The attributes filter rule `{0}` is not in the right format. It '
            'must be one of: <key>=<value>, <key>!=<value>, '
            '<key> contains <value>, <key> does-not-contain <value>, '
            '<key> starts-with <value>, <key> ends-with <value>, '
            '<key> is not empty. <value> can be a single string or a list of '
            'strings of the form [<value1>,<value2>,...]'.format(
                labels_filter_value)
        )


class FilterRule(dict):
    def __init__(self, key, values, operator, filter_rule_type):
        super(FilterRule, self).__init__()
        self['key'] = key
        self['values'] = values
        self['operator'] = OPERATOR_MAPPING[operator]
        self['type'] = filter_rule_type


class LabelsFilterRule(FilterRule):
    def __init__(self, key, values, operator):
        super(LabelsFilterRule, self).__init__(key, values, operator, 'label')


class AttrsFilterRule(FilterRule):
    def __init__(self, key, values, operator):
        super(AttrsFilterRule, self).__init__(key, values, operator,
                                              'attribute')


def create_filter(resource_name,
                  filter_id,
                  labels_rules,
                  attrs_rules,
                  visibility,
                  tenant_name,
                  logger,
                  filters_client):
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)

    filter_rules = get_filter_rules(labels_rules, attrs_rules)
    try:
        new_filter = filters_client.create(filter_id, filter_rules, visibility)
    except InvalidFilterRule as e:
        e._message = _modify_err_msg(e.err_filter_rule, e.err_reason)
        raise e

    logger.info("{0}' filter `{1}` created".format(resource_name.capitalize(),
                                                   new_filter.id))


def get_filter(resource_name, filter_id, tenant_name, logger, client):
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = NOT_FOUND_MSG.format(resource_name, filter_id)
    with handle_client_error(404, graceful_msg, logger):
        logger.info("Getting info for {0}' filter `{1}`...".format(
            resource_name, filter_id))
        filter_details = client.get(filter_id)
        _modify_filter_details(filter_details)
        print_details(filter_details,
                      "Requested {0}' filter info:".format(resource_name))


def update_filter(resource_name,
                  filter_id,
                  labels_rules,
                  attrs_rules,
                  visibility,
                  tenant_name,
                  logger,
                  filters_client):
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)
    graceful_msg = NOT_FOUND_MSG.format(resource_name, filter_id)
    filter_rules = get_filter_rules(labels_rules, attrs_rules)
    with handle_client_error(404, graceful_msg, logger):
        try:
            new_filter = filters_client.update(filter_id,
                                               filter_rules,
                                               visibility)
        except InvalidFilterRule as e:
            e._message = _modify_err_msg(e.err_filter_rule, e.err_reason)
            raise e
        logger.info('{0} filter `{1}` updated'.format(
            resource_name.capitalize(), new_filter.id))


def delete_filter(resource_name, filter_id, tenant_name, logger, client):
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = NOT_FOUND_MSG.format(resource_name, filter_id)
    with handle_client_error(404, graceful_msg, logger):
        logger.info("Deleting {0}' filter `{1}`...".format(resource_name,
                                                           filter_id))
        client.delete(filter_id)
        logger.info('Filter removed')


def list_filters(resource_name,
                 sort_by,
                 descending,
                 tenant_name,
                 all_tenants,
                 search,
                 pagination_offset,
                 pagination_size,
                 logger,
                 filters_client):
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info("Listing all {0}' filters...".format(resource_name))
    filters_list_res = filters_client.list(
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
    filter_details['attrs_filter_rules'] = _filter_rules_to_string(
        filter_details['attrs_filter_rules'])
    filter_details['labels_filter_rules'] = _filter_rules_to_string(
        filter_details['labels_filter_rules'])


def create_labels_filter_rules_list(labels_filter_rules_string):
    """Validate and parse a string of labels filter rules

    :param labels_filter_rules_string: A string of filter rules of type `label`
           separated with an `and`.
    :return The list of filter rules that matches the provided string.
    """
    labels_filter_rules = []
    raw_labels_filter_rules = labels_filter_rules_string.split(' and ')
    for labels_filter in raw_labels_filter_rules:
        if '!=' in labels_filter:
            key, values = _parse_filter_rule(
                labels_filter, '!=', BadLabelsFilterRule)
            labels_filter_rules.append(LabelsFilterRule(key, values, '!='))

        elif '=' in labels_filter:
            key, values = _parse_filter_rule(
                labels_filter, '=', BadLabelsFilterRule)
            labels_filter_rules.append(LabelsFilterRule(key, values, '='))

        elif 'null' in labels_filter:
            match_null = re.match(r'(\S+) is null', labels_filter)
            match_not_null = re.match(r'(\S+) is not null', labels_filter)
            if match_null:
                key = match_null.group(1).lower()
                labels_filter_rules.append(
                    LabelsFilterRule(key, [], 'is null'))
            elif match_not_null:
                key = match_not_null.group(1).lower()
                labels_filter_rules.append(
                    LabelsFilterRule(key, [], 'is not null'))
            else:
                raise BadLabelsFilterRule(labels_filter)

        else:
            raise BadLabelsFilterRule(labels_filter)

    return labels_filter_rules


def create_attributes_filter_rules_list(attributes_filter_rules_string):
    """Validate and parse a list of attributes filter rules

    :param attributes_filter_rules_string: A string of filter rules of type
           `attribute` separated with an `and`.
    :return The list of filter rules that matches the provided string.
    """
    attrs_filter_rules = []
    raw_attrs_filter_rules = attributes_filter_rules_string.split(' and ')
    for attrs_filter in raw_attrs_filter_rules:
        for sign in ['!=', '=', 'contains', 'does-not-contain',
                     'starts-with', 'ends-with']:
            if sign in attrs_filter:
                key, values = _parse_filter_rule(attrs_filter, sign,
                                                 BadAttributesFilterRule)
                attrs_filter_rules.append(AttrsFilterRule(key, values, sign))
                break
        else:
            match_not_empty = re.match(r'(\S+) is not empty', attrs_filter)
            if match_not_empty:
                key = match_not_empty.group(1).lower()
                attrs_filter_rules.append(
                    AttrsFilterRule(key, [], 'is not empty'))
            else:
                raise BadAttributesFilterRule(attrs_filter)

    return attrs_filter_rules


def _parse_filter_rule(filter_rule, sign, filter_rule_err_class):
    """Parse a filter rule

    :param filter_rule: One of:
           <key>=<value>,<key>=[<value1>,<value2>,...],
           <key>!=<value>, <key>!=[<value1>,<value2>,...],
           <key> contains <value>, <key> contains [<value1>,<value2>,..],
           <key> does-not-contain  <value>,
           <key> does-not-contain [<value1>,<value2>,..],
           <key> starts-with <value>, <key> starts-with [<value1>,<value2>,..],
           <key> ends-with <value>, <key> ends-with [<value1>,<value2>,..],
    :param sign: Either '=' / '!=' / 'contains' / 'not-contains' /
           'starts-with' / 'ends-with'
    :param filter_rule_err_class: BadLabelsFilterRule / BadAttributesFilterRule
    :return: The filter_rule's key and value(s) stripped of whitespaces
    """
    try:
        raw_label_key, raw_label_value = filter_rule.split(sign)
    except ValueError:  # e.g. a=b=c
        raise filter_rule_err_class(filter_rule)

    label_key = raw_label_key.strip()
    label_values = _get_label_value(raw_label_value.strip())

    return label_key, label_values


def _get_label_value(raw_label_value):
    if raw_label_value.startswith('[') and raw_label_value.endswith(']'):
        return raw_label_value.strip('[]').split(',')

    return [raw_label_value]


def get_filter_rules(labels_filter_rules, attrs_filter_rules):
    filter_rules = []
    if labels_filter_rules:
        filter_rules.extend(labels_filter_rules)
    if attrs_filter_rules:
        filter_rules.extend(attrs_filter_rules)

    return filter_rules


def _filter_rules_to_string(filter_rules):
    """Map the filter rules list to a string of filter rules"""
    if not filter_rules:
        return None

    filter_rules_str_list = []
    for filter_rule in filter_rules:
        filter_rule_key = filter_rule['key']
        filter_rule_operator = filter_rule['operator']
        cli_operator = REVERSED_OPERATOR_MAPPING[filter_rule_operator]
        if filter_rule_operator in ('is_null', 'is_not_null', 'is_not_empty'):
            filter_rule_str = '{key} {operator}'.format(key=filter_rule_key,
                                                        operator=cli_operator)
        else:
            if filter_rule_operator in ('starts_with', 'ends_with', 'contains',
                                        'not_contains'):
                cli_operator = ' {0} '.format(cli_operator)

            if len(filter_rule['values']) == 1:
                filter_rule_str = '{key}{operator}{values}'.format(
                    key=filter_rule['key'], operator=cli_operator,
                    values=filter_rule['values'][0])
            else:
                filter_rule_str = '{key}{operator}[{values}]'.format(
                    key=filter_rule['key'], operator=cli_operator,
                    values=','.join(filter_rule['values']))

        filter_rules_str_list.append(filter_rule_str)

    return '\"{0}\"'.format(' and '.join(filter_rules_str_list))


def _modify_err_msg(err_filter_rule, err_reason):
    str_filter_rule = _filter_rules_to_string([err_filter_rule])
    return 'The filter rule {0} is invalid. {1}'.format(str_filter_rule,
                                                        err_reason)
