from __future__ import unicode_literals

from mock import Mock
from collections import OrderedDict

from cloudify_rest_client.filters import Filter

from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.filters_utils import (InvalidLabelsFilterRuleFormat,
                                        InvalidAttributesFilterRuleFormat)

from .mocks import MockListResponse
from .test_base import CliCommandTest

MATCHING_LABELS_RULES = OrderedDict([
    ('a="b and c"', {'key': 'a', 'values': ['b and c'], 'operator': 'any_of',
                     'type': 'label'}),
    ('c=["d,e\\,f"]', {'key': 'c', 'values': ['d', 'e,f'],
                       'operator': 'any_of', 'type': 'label'}),
    ('f!=g', {'key': 'f', 'values': ['g'], 'operator': 'not_any_of',
              'type': 'label'}),
    ('h!=["i:,j k\xf3"]', {'key': 'h', 'values': ['i:', 'j k\xf3'],
                           'operator': 'not_any_of', 'type': 'label'}),
    ('"k_l is null"', {'key': 'k_l', 'values': [], 'operator': 'is_null',
                       'type': 'label'}),
    ('"l_m-n.o is not null"', {'key': 'l_m-n.o', 'values': [],
                               'operator': 'is_not_null', 'type': 'label'})
])

# These are not real attributes, but it doesn't matter for the CLI tests
MATCHING_ATTRS_RULES = OrderedDict([
    ('a=b', {'key': 'a', 'values': ['b'], 'operator': 'any_of',
             'type': 'attribute'}),
    ('c=[d,e]', {'key': 'c', 'values': ['d', 'e'], 'operator': 'any_of',
                 'type': 'attribute'}),
    ('f!=g', {'key': 'f', 'values': ['g'], 'operator': 'not_any_of',
              'type': 'attribute'}),
    ('h!=[i,j]', {'key': 'h', 'values': ['i', 'j'], 'operator': 'not_any_of',
                  'type': 'attribute'}),
    ('"k contains l"', {'key': 'k', 'values': ['l'], 'operator': 'contains',
                        'type': 'attribute'}),
    ('"m contains [n,o]"', {'key': 'm', 'values': ['n', 'o'],
                            'operator': 'contains', 'type': 'attribute'}),
    ('"p does-not-contain q"',
     {'key': 'p', 'values': ['q'], 'operator': 'not_contains',
      'type': 'attribute'}),
    ('"r does-not-contain [s,t]"',
     {'key': 'r', 'values': ['s', 't'], 'operator': 'not_contains',
      'type': 'attribute'}),
    ('"u starts-with v"', {'key': 'u', 'values': ['v'],
                           'operator': 'starts_with', 'type': 'attribute'}),
    ('"w starts-with [x,y]"',
     {'key': 'w', 'values': ['x', 'y'], 'operator': 'starts_with',
      'type': 'attribute'}),
    ('"z ends-with aa"', {'key': 'z', 'values': ['aa'],
                          'operator': 'ends_with', 'type': 'attribute'}),
    ('"ab ends-with [ac,ad]"', {'key': 'ab', 'values': ['ac', 'ad'],
                                'operator': 'ends_with', 'type': 'attribute'}),
    ('"a-e is not empty"', {'key': 'a-e', 'values': [],
                            'operator': 'is_not_empty', 'type': 'attribute'})
])

FILTER_ID = 'filter'


class FiltersTest(CliCommandTest):
    __test__ = False

    def setUp(self, resource):
        super(FiltersTest, self).setUp()
        self.use_manager()
        self.resource = resource
        self.prefix = 'cfy {resource} filters'.format(resource=resource)
        self.resource_client = getattr(self.client, resource)
        self.filters_client = getattr(self.client,
                                      '{}_filters'.format(resource))
        self.example_filter = Filter({
            'id': 'filter1',
            'visibility': 'tenant',
            'created_at': '2021-04-05T15:25:40.310Z',
            'value': [
                {'key': 'key', 'values': ['va, l\xf3e'], 'operator': 'any_of',
                 'type': 'label'},
                {'key': 'ke.y', 'values': ['val:$'], 'operator': 'any_of',
                 'type': 'label'},
                {'key': 'created_by', 'values': ['val-u.e'],
                 'operator': 'not_any_of', 'type': 'attribute'}],
            'updated_at': '2021-04-05T15:25:40.310Z',
            'is_system_filter': False,
            'tenant_name': 'default_tenant',
            'created_by': 'admin',
            'resource_availability': 'tenant',
            'private_resource': False,
            'labels_filter_rules': [
                {'key': 'key', 'values': ['va, l\xf3e'], 'operator': 'any_of',
                 'type': 'label'},
                {'key': 'ke.y', 'values': ['val:$'],
                 'operator': 'any_of', 'type': 'label'}
            ],
            'attrs_filter_rules': [
                {'key': 'created_by', 'values': ['val-u.e'],
                 'operator': 'any_of', 'type': 'attribute'}
            ]
        })

    def test_create_filters(self):
        self.filters_client.create = Mock()
        cmd_prefix = self.prefix + ' create ' + FILTER_ID
        labels_rules = ' -lr '.join(MATCHING_LABELS_RULES.keys())
        attrs_rules = ' -ar '.join(MATCHING_ATTRS_RULES.keys())
        self.invoke('{0} -lr {1} -ar {2}'.format(cmd_prefix, labels_rules,
                                                 attrs_rules))

        call_args = list(self.filters_client.create.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)
        self.assertEqual(call_args[0][1],
                         list(MATCHING_LABELS_RULES.values()) +
                         list(MATCHING_ATTRS_RULES.values()))

    def test_create_filters_missing_filter_id(self):
        cmd = '{} create'.format(self.prefix)
        self._test_missing_argument(cmd, 'FILTER_ID')

    def test_create_filters_invalid_filter_rules(self):
        self._test_providing_invalid_filter_rules('create')

    def test_get_filters(self):
        cmd = '{0} get {1}'.format(self.prefix, FILTER_ID)
        self.filters_client.get = Mock()
        self.invoke(cmd)
        call_args = list(self.filters_client.get.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)

    def test_get_filters_missing_filter_id(self):
        self._test_missing_argument('{} get'.format(self.prefix), 'FILTER_ID')

    def test_filters_list(self):
        self.filters_client.list = Mock(return_value=MockListResponse(
            items=[self.example_filter]))
        raw_output = self.invoke('{} list'.format(self.prefix)).output
        call_args = list(self.filters_client.list.call_args)
        self.assertEqual(call_args[1],
                         {'sort': 'id', 'is_descending': False,
                          '_all_tenants': False, '_search': None,
                          '_offset': 0, '_size': 1000})
        self.assertIn('"key=va\\, l\xf3e","ke.y=val\\:\\$"', raw_output)
        self.assertIn('"created_by=val-u.e"', raw_output)

    def test_filters_update(self):
        self.filters_client.update = Mock()
        cmd_prefix = self.prefix + ' update ' + FILTER_ID
        labels_rules = ' -lr '.join(MATCHING_LABELS_RULES.keys())
        attrs_rules = ' -ar '.join(MATCHING_ATTRS_RULES.keys())
        cmd_with_filter_rules = '{0} -lr {1} -ar {2}'.format(
            cmd_prefix, labels_rules, attrs_rules)
        cmd_with_visibility = '{cmd_prefix} update {filter_id} --visibility ' \
                              'global'.format(cmd_prefix=self.prefix,
                                              filter_id=FILTER_ID)
        cmd_with_filter_rules_and_visibility = \
            cmd_with_filter_rules + ' --visibility global'

        self.invoke(cmd_with_filter_rules)
        call_args = list(self.filters_client.update.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)
        self.assertEqual(call_args[0][1],
                         list(MATCHING_LABELS_RULES.values()) +
                         list(MATCHING_ATTRS_RULES.values()))
        self.assertEqual(call_args[0][2], None)

        self.invoke(cmd_with_visibility)
        call_args = list(self.filters_client.update.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)
        self.assertEqual(call_args[0][1], [])
        self.assertEqual(call_args[0][2], 'global')

        self.invoke(cmd_with_filter_rules_and_visibility)
        call_args = list(self.filters_client.update.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)
        self.assertEqual(call_args[0][1],
                         list(MATCHING_LABELS_RULES.values()) +
                         list(MATCHING_ATTRS_RULES.values()))
        self.assertEqual(call_args[0][2], 'global')

    def test_filters_update_invalid_filter_rules(self):
        self._test_providing_invalid_filter_rules('update')

    def test_filters_update_invalid_visibility(self):
        self.invoke(
            '{} update filter --visibility bla'.format(self.prefix),
            err_str_segment='Invalid visibility: `bla`',
            exception=CloudifyCliError
        )

    def test_filters_delete(self):
        self.filters_client.delete = Mock()
        self.invoke('{0} delete {1}'.format(self.prefix, FILTER_ID))
        call_args = list(self.filters_client.delete.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)

    def test_delete_filters_missing_filter_id(self):
        self._test_missing_argument('{} delete'.format(self.prefix),
                                    'FILTER_ID')

    def test_list_with_filters(self):
        self.resource_client.list = Mock(
            return_value=MockListResponse()
        )
        self.invoke('cfy {resource} list --filter-id {filter_id} '
                    '-ar {attrs_rules} -lr {labels_rules}'.format(
                     resource=self.resource, filter_id=FILTER_ID,
                     attrs_rules=' -ar '.join(MATCHING_ATTRS_RULES.keys()),
                     labels_rules=' -lr '.join(MATCHING_LABELS_RULES.keys())))

        call_args = list(self.resource_client.list.call_args)
        call_args[1]['filter_rules'] = (list(MATCHING_LABELS_RULES.values()) +
                                        list(MATCHING_ATTRS_RULES.values()))
        call_args[1]['filter_id'] = FILTER_ID

    def test_list_with_invalid_filters(self):
        self._test_providing_invalid_filter_rules(
            'list', 'cfy {0}'.format(self.resource))

    def _test_missing_argument(self, command, argument):
        outcome = self.invoke(
            command,
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('missing argument', outcome.output.lower())
        self.assertIn(argument, outcome.output)

    def _test_providing_invalid_filter_rules(self, command, prefix=None):
        prefix = prefix or self.prefix
        invalid_labels_rules = [
            'ke%y=value',
            '"key!=val\tue"',
            '"key&value"',
            '"key is value"',
        ]
        invalid_attrs_rules = invalid_labels_rules + [
            '"key=val&ue"',
            '"key=[value"',
            '"key=[va\\,lue]"',
        ]

        for labels_rule in invalid_labels_rules:
            cmd = '{0} {1} -lr {2}'.format(prefix, command, labels_rule)
            self.invoke(
                cmd,
                err_str_segment='labels filter rule `{0}`'.format(
                    labels_rule.strip('""')),
                exception=InvalidLabelsFilterRuleFormat
            )

        for attrs_rule in invalid_attrs_rules:
            cmd = '{0} {1} -ar {2}'.format(prefix, command, attrs_rule)
            self.invoke(
                cmd,
                err_str_segment='attributes filter rule `{0}`'.format(
                    attrs_rule.strip('""')),
                exception=InvalidAttributesFilterRuleFormat
            )


class BlueprintsFiltersTest(FiltersTest):
    __test__ = True

    def setUp(self):
        super(BlueprintsFiltersTest, self).setUp('blueprints')


class DeploymentsFiltersTest(FiltersTest):
    __test__ = True

    def setUp(self):
        super(DeploymentsFiltersTest, self).setUp('deployments')
