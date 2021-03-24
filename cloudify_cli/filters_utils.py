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


class InvalidLabelsFilterRuleFormat(CloudifyCliError):
    def __init__(self, labels_filter_value):
        super(CloudifyCliError, self).__init__(
            'The labels filter rule `{0}` is not in the right format. It must '
            'be one of: <key>=<value>, <key>!=<value>, <key> is null, '
            '<key> is not null. <value> can be a single string or a list of '
            'strings of the form [<value1>,<value2>,...]'.format(
                labels_filter_value)
        )


class InvalidAttributesFilterRuleFormat(CloudifyCliError):
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
    format_exception = None

    def __init__(self, key, values, operator, filter_rule_type):
        super(FilterRule, self).__init__()
        self['key'] = key
        self['values'] = values
        self['operator'] = OPERATOR_MAPPING[operator]
        self['type'] = filter_rule_type

    @classmethod
    def _parse_filter_rule(cls, str_filter_rule, operator):
        """Parse a filter rule

        :param str_filter_rule: One of:
               <key>=<value>,<key>=[<value1>,<value2>,...],
               <key>!=<value>, <key>!=[<value1>,<value2>,...],
               <key> contains <value>, <key> contains [<value1>,<value2>,..],
               <key> does-not-contain  <value>,
               <key> does-not-contain [<value1>,<value2>,..],
               <key> starts-with <value>, <key> starts-with [<value1>,
               <value2>,..],
               <key> ends-with <value>, <key> ends-with [<value1>,<value2>,..],
        :param operator: Either '=' / '!=' / 'contains' / 'not-contains' /
               'starts-with' / 'ends-with'
        :return: The filter_rule's key and value(s) stripped of whitespaces
        """
        try:
            raw_rule_key, raw_rule_value = str_filter_rule.split(operator)
        except ValueError:  # e.g. a=b=c
            raise cls.format_exception(str_filter_rule)

        rule_key = raw_rule_key.strip()
        rule_values = cls._get_rule_values(raw_rule_value.strip())

        return rule_key, rule_values

    @staticmethod
    def _get_rule_values(raw_rule_value):
        if raw_rule_value.startswith('[') and raw_rule_value.endswith(']'):
            return raw_rule_value.strip('[]').split(',')

        return [raw_rule_value]

    def __str__(self, cli_operator):
        if len(self['values']) == 1:
            return '{key}{operator}{values}'.format(key=self['key'],
                                                    operator=cli_operator,
                                                    values=self['values'][0])

        return '{key}{operator}[{values}]'.format(
            key=self['key'], operator=cli_operator,
            values=','.join(self['values']))


class LabelsFilterRule(FilterRule):
    format_exception = InvalidLabelsFilterRuleFormat

    def __init__(self, key, values, operator):
        super(LabelsFilterRule, self).__init__(key, values, operator, 'label')

    @classmethod
    def from_string(cls, str_filter_rule):
        if '!=' in str_filter_rule:
            key, values = cls._parse_filter_rule(str_filter_rule, '!=')
            return cls(key, values, '!=')

        elif '=' in str_filter_rule:
            key, values = cls._parse_filter_rule(str_filter_rule, '=')
            return cls(key, values, '=')

        elif 'null' in str_filter_rule:
            match_null = re.match(r'(\S+) is null', str_filter_rule)
            match_not_null = re.match(r'(\S+) is not null', str_filter_rule)
            if match_null:
                key = match_null.group(1).lower()
                return cls(key, [], 'is null')
            elif match_not_null:
                key = match_not_null.group(1).lower()
                return cls(key, [], 'is not null')
            else:
                raise cls.format_exception(str_filter_rule)

        else:
            raise cls.format_exception(str_filter_rule)

    def __str__(self):
        cli_operator = REVERSED_OPERATOR_MAPPING[self['operator']]
        if self['operator'] in ('is_null', 'is_not_null'):
            return '{0} {1}'.format(self['key'], cli_operator)

        return super(LabelsFilterRule, self).__str__(cli_operator)


class AttrsFilterRule(FilterRule):
    format_exception = InvalidAttributesFilterRuleFormat

    def __init__(self, key, values, operator):
        super(AttrsFilterRule, self).__init__(key, values, operator,
                                              'attribute')

    @classmethod
    def from_string(cls, str_filter_rule):
        for operator in ['!=', '=', 'contains', 'does-not-contain',
                         'starts-with', 'ends-with']:
            if operator in str_filter_rule:
                key, values = cls._parse_filter_rule(str_filter_rule, operator)
                return cls(key, values, operator)

        # None of the operators in the list is in str_filter_rule
        match_not_empty = re.match(r'(\S+) is not empty', str_filter_rule)
        if match_not_empty:
            key = match_not_empty.group(1).lower()
            return cls(key, [], 'is not empty')

        else:
            raise cls.format_exception(str_filter_rule)

    def __str__(self):
        filter_rule_operator = self['operator']
        cli_operator = REVERSED_OPERATOR_MAPPING[filter_rule_operator]
        if filter_rule_operator == 'is_not_empty':
            return '{key} {operator}'.format(key=self['key'],
                                             operator=cli_operator)
        if filter_rule_operator in ('starts_with', 'ends_with', 'contains',
                                    'not_contains'):
            cli_operator = ' {0} '.format(cli_operator)

        return super(AttrsFilterRule, self).__str__(cli_operator)


def create_filter(resource_name,
                  filter_id,
                  filter_rules,
                  visibility,
                  tenant_name,
                  logger,
                  filters_client):
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)

    try:
        new_filter = filters_client.create(filter_id, filter_rules, visibility)
    except InvalidFilterRule as e:
        e._message = _modify_err_msg(e.err_filter_rule, e.err_reason)
        raise e

    logger.info("%s' filter `%s` created", resource_name.capitalize(),
                new_filter.id)


def get_filter(resource_name, filter_id, tenant_name, logger, client):
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = NOT_FOUND_MSG.format(resource_name, filter_id)
    with handle_client_error(404, graceful_msg, logger):
        logger.info("Getting info for %s' filter `%s`...", resource_name,
                    filter_id)
        filter_details = client.get(filter_id)
        _modify_filter_details(filter_details)
        print_details(filter_details,
                      "Requested {0}' filter info:".format(resource_name))


def update_filter(resource_name,
                  filter_id,
                  filter_rules,
                  visibility,
                  tenant_name,
                  logger,
                  filters_client):
    utils.explicit_tenant_name_message(tenant_name, logger)
    validate_visibility(visibility)
    graceful_msg = NOT_FOUND_MSG.format(resource_name, filter_id)
    with handle_client_error(404, graceful_msg, logger):
        try:
            new_filter = filters_client.update(filter_id,
                                               filter_rules,
                                               visibility)
        except InvalidFilterRule as e:
            e._message = _modify_err_msg(e.err_filter_rule, e.err_reason)
            raise e
        logger.info('%s filter `%s` updated', resource_name.capitalize(),
                    new_filter.id)


def delete_filter(resource_name, filter_id, tenant_name, logger, client):
    utils.explicit_tenant_name_message(tenant_name, logger)
    graceful_msg = NOT_FOUND_MSG.format(resource_name, filter_id)
    with handle_client_error(404, graceful_msg, logger):
        logger.info("Deleting %s' filter `%s`...", resource_name, filter_id)
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
    logger.info("Listing all %s' filters...", resource_name)
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
    logger.info('Showing %s of %s filters', len(filters_list_res), total)


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
    raw_labels_filter_rules = labels_filter_rules_string.split(' and ')
    labels_filter_rules = [LabelsFilterRule.from_string(raw_filter_rule) for
                           raw_filter_rule in raw_labels_filter_rules]

    return labels_filter_rules


def create_attributes_filter_rules_list(attributes_filter_rules_string):
    """Validate and parse a list of attributes filter rules

    :param attributes_filter_rules_string: A string of filter rules of type
           `attribute` separated with an `and`.
    :return The list of filter rules that matches the provided string.
    """
    raw_attrs_filter_rules = attributes_filter_rules_string.split(' and ')
    attrs_filter_rules = [AttrsFilterRule.from_string(raw_filter_rule) for
                          raw_filter_rule in raw_attrs_filter_rules]

    return attrs_filter_rules


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

    str_filter_rules_list = []
    for raw_filter_rule in filter_rules:
        if raw_filter_rule['type'] == 'label':
            filter_rule = LabelsFilterRule(raw_filter_rule['key'],
                                           raw_filter_rule['values'],
                                           raw_filter_rule['operator'])
        else:
            filter_rule = AttrsFilterRule(raw_filter_rule['key'],
                                          raw_filter_rule['values'],
                                          raw_filter_rule['operator'])

        str_filter_rules_list.append(str(filter_rule))

    return '"{0}"'.format(' and '.join(str_filter_rules_list))


def _modify_err_msg(err_filter_rule, err_reason):
    str_filter_rule = _filter_rules_to_string([err_filter_rule])
    return 'The filter rule {0} is invalid. {1}'.format(str_filter_rule,
                                                        err_reason)
