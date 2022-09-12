import re

from cloudify_cli import utils
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.table import print_data, print_details
from cloudify_cli.utils import validate_visibility, handle_client_error

from cloudify_rest_client.exceptions import InvalidFilterRule

FILTERS_COLUMNS = ['id', 'labels_filter_rules', 'attrs_filter_rules',
                   'created_at', 'updated_at', 'visibility',
                   'tenant_name', 'created_by']

NOT_FOUND_MSG = 'Requested {0} filter with ID `{1}` was not found in ' \
                'this tenant'

OPERATOR_MAPPING = {
    '=': 'any_of',
    '!=': 'not_any_of',
    'is-not': 'is_not',
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
            'be one of: <key>=<value>, <key>!=<value>, <key> is-not <value>,'
            ' <key> is null, <key> is not null. <value> can be a single '
            'string or a list of strings of the form [<value1>,<value2>,...]. '
            '<value> cannot contain control characters, plus, any comma and '
            'colon in <value> must be escaped with `\\`. <key> can '
            'contain only letters, digits and the characters '
            '`-`, `.` and `_`'.format(labels_filter_value)
        )


class InvalidAttributesFilterRuleFormat(CloudifyCliError):
    def __init__(self, labels_filter_value):
        super(CloudifyCliError, self).__init__(
            'The attributes filter rule `{0}` is not in the right format. It '
            'must be one of: <key>=<value>, <key>!=<value>, '
            '<key> contains <value>, <key> does-not-contain <value>, '
            '<key> starts-with <value>, <key> ends-with <value>, '
            '<key> is not empty. <value> can be a single string or a list of '
            'strings of the form [<value1>,<value2>,...]. <key> and <value> '
            'can contain only letters, digits and the characters `-`, `.` '
            'and `_`'.format(labels_filter_value)
        )


class FilterRule(dict):
    def __init__(self, key, values, operator, filter_rule_type):
        super(FilterRule, self).__init__()
        self['key'] = key
        self['values'] = values
        self['operator'] = operator
        self['type'] = filter_rule_type

    @staticmethod
    def _get_rule_values(raw_rule_value):
        raw_rule_value = raw_rule_value.replace('\\,', '\x00')
        if raw_rule_value.startswith('[') and raw_rule_value.endswith(']'):
            raw_values_list = raw_rule_value.strip('[]').split(',')
        else:
            raw_values_list = [raw_rule_value]

        return [value.replace('\x00', ',').replace('\\:', ':')
                for value in raw_values_list]

    def __str__(self, cli_operator):
        values = (self['values'][0] if len(self['values']) == 1 else
                  u'[{0}]'.format(','.join(self['values'])))
        return '"{key}{operator}{values}"'.format(key=self['key'],
                                                  operator=cli_operator,
                                                  values=values)


class LabelsFilterRule(FilterRule):
    def __init__(self, key, values, operator):
        super(LabelsFilterRule, self).__init__(key, values, operator, 'label')

    @classmethod
    def from_string(cls, str_filter_rule):
        for operator in ['!=', '=', ' is-not ']:
            matching = re.match(
                r'^([\w\-\.]+)({0})([^\n\t\"]+)$'.format(operator),
                str_filter_rule)
            if matching:
                key = matching.group(1).lower()
                operator = matching.group(2)
                values = cls._get_rule_values(matching.group(3))
                return cls(key, values, OPERATOR_MAPPING[operator.strip()])

        match_null = re.match(r'^([\w\-\.]+) (is null)$', str_filter_rule)
        match_not_null = re.match(r'^([\w\-\.]+) (is not null)$',
                                  str_filter_rule)
        null_matching = match_null or match_not_null

        if null_matching:
            key = null_matching.group(1).lower()
            operator = null_matching.group(2)
            return cls(key, [], OPERATOR_MAPPING[operator])

        # If we got here, the labels filter is not in the right format
        raise InvalidLabelsFilterRuleFormat(str_filter_rule)

    def __str__(self):
        cli_operator = REVERSED_OPERATOR_MAPPING[self['operator']]
        if self['operator'] in ('is_null', 'is_not_null'):
            return '"{0} {1}"'.format(self['key'], cli_operator)
        if cli_operator == 'is-not':
            cli_operator = ' is-not '
        self['values'] = [val.replace(',', '\\,').replace(':', '\\:')
                          .replace('$', '\\$') for val in self['values']]
        return super(LabelsFilterRule, self).__str__(cli_operator)


class AttrsFilterRule(FilterRule):
    def __init__(self, key, values, operator):
        super(AttrsFilterRule, self).__init__(key, values, operator,
                                              'attribute')

    @classmethod
    def from_string(cls, str_filter_rule):
        for operator in ['!=', '=', ' contains ', ' does-not-contain ',
                         ' starts-with ', ' ends-with ']:
            matching = re.match(
                r'^([\w\-\.]+)({0})([\w\-\.]+|\[[\w\-\.\,]+\])$'.format(
                    operator), str_filter_rule)
            if matching:
                key = matching.group(1).lower()
                operator = matching.group(2)
                values = cls._get_rule_values(matching.group(3))
                return cls(key, values, OPERATOR_MAPPING[operator.strip()])

        # The str_filter_rule didn't match the pattern with any operator
        match_not_empty = re.match(r'^([\w\-\.]+) is not empty$',
                                   str_filter_rule)
        if match_not_empty:
            key = match_not_empty.group(1).lower()
            return cls(key, [], OPERATOR_MAPPING['is not empty'])

        raise InvalidAttributesFilterRuleFormat(str_filter_rule)

    def __str__(self):
        filter_rule_operator = self['operator']
        cli_operator = REVERSED_OPERATOR_MAPPING[filter_rule_operator]
        if filter_rule_operator == 'is_not_empty':
            return '"{key} {operator}"'.format(key=self['key'],
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
        labels_filter_rules = filter_details['labels_filter_rules']
        attrs_filter_rules = filter_details['attrs_filter_rules']
        if labels_filter_rules and isinstance(labels_filter_rules, list):
            filter_details['labels_filter_rules'] = ', '.join(
                labels_filter_rules)
        if attrs_filter_rules and isinstance(attrs_filter_rules, list):
            filter_details['attrs_filter_rules'] = ', '.join(
                attrs_filter_rules)
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


def create_labels_filter_rules_list(raw_labels_filter_rules_list):
    """Validate and parse a string of labels filter rules

    :param raw_labels_filter_rules_list: A list of filter rules of type
           `label`, formatted as strings.
    :return The list of filter rules that matches the provided string.
    """
    labels_filter_rules = [LabelsFilterRule.from_string(raw_filter_rule) for
                           raw_filter_rule in raw_labels_filter_rules_list]

    return labels_filter_rules


def create_attributes_filter_rules_list(raw_attributes_filter_rules_list):
    """Validate and parse a list of attributes filter rules

    :param raw_attributes_filter_rules_list: A list of filter rules of type
           `attribute`, formatted as strings.
    :return The list of filter rules that matches the provided string.
    """
    attrs_filter_rules = [AttrsFilterRule.from_string(raw_filter_rule) for
                          raw_filter_rule in raw_attributes_filter_rules_list]

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

    return (str_filter_rules_list[0] if len(str_filter_rules_list) == 1
            else str_filter_rules_list)


def _modify_err_msg(err_filter_rule, err_reason):
    str_filter_rule = _filter_rules_to_string([err_filter_rule])
    return 'The filter rule `{0}` is invalid. {1}'.format(str_filter_rule,
                                                          err_reason)
