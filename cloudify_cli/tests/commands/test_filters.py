from mock import MagicMock

from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.filters_utils import (BadLabelsFilterRule,
                                        BadAttributesFilterRule)

from .mocks import MockListResponse
from .test_base import CliCommandTest

LABELS_RULES_STR = "a=b and c=[d,e] and f!=g and h!=[i,j] and k is null " \
                   "and l is not null"
LABELS_RULES_LIST = [
    {'key': 'a', 'values': ['b'], 'operator': 'any_of', 'type': 'label'},
    {'key': 'c', 'values': ['d', 'e'], 'operator': 'any_of',
     'type': 'label'},
    {'key': 'f', 'values': ['g'], 'operator': 'not_any_of',
     'type': 'label'},
    {'key': 'h', 'values': ['i', 'j'], 'operator': 'not_any_of',
     'type': 'label'},
    {'key': 'k', 'values': [], 'operator': 'is_null', 'type': 'label'},
    {'key': 'l', 'values': [], 'operator': 'is_not_null', 'type': 'label'},
]

# This are not real attributes, but it doesn't matter for the CLI tests
ATTRS_RULES_STR = "a=b and c=[d,e] and f!=g and h!=[i,j] and " \
                  "k contains l and m contains [n,o] and " \
                  "p does-not-contain q and r does-not-contain [s,t] " \
                  "and u starts-with v and w starts-with [x,y] and " \
                  "z ends-with aa and ab ends-with [ac,ad] and " \
                  "ae is not empty"
ATTRS_RULES_LIST = [
    {'key': 'a', 'values': ['b'], 'operator': 'any_of',
     'type': 'attribute'},
    {'key': 'c', 'values': ['d', 'e'], 'operator': 'any_of',
     'type': 'attribute'},
    {'key': 'f', 'values': ['g'], 'operator': 'not_any_of',
     'type': 'attribute'},
    {'key': 'h', 'values': ['i', 'j'], 'operator': 'not_any_of',
     'type': 'attribute'},
    {'key': 'k', 'values': ['l'], 'operator': 'contains',
     'type': 'attribute'},
    {'key': 'm', 'values': ['n', 'o'], 'operator': 'contains',
     'type': 'attribute'},
    {'key': 'p', 'values': ['q'], 'operator': 'not_contains',
     'type': 'attribute'},
    {'key': 'r', 'values': ['s', 't'], 'operator': 'not_contains',
     'type': 'attribute'},
    {'key': 'u', 'values': ['v'], 'operator': 'starts_with',
     'type': 'attribute'},
    {'key': 'w', 'values': ['x', 'y'], 'operator': 'starts_with',
     'type': 'attribute'},
    {'key': 'z', 'values': ['aa'], 'operator': 'ends_with',
     'type': 'attribute'},
    {'key': 'ab', 'values': ['ac', 'ad'], 'operator': 'ends_with',
     'type': 'attribute'},
    {'key': 'ae', 'values': [], 'operator': 'is_not_empty',
     'type': 'attribute'},
]

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

    def test_create_filters(self):
        self.filters_client.create = MagicMock()
        self.invoke(
            '{cmd_prefix} create {filter_id} --labels-rules "{labels_rules}" '
            '--attrs-rules "{attrs_rules}"'.format(
                cmd_prefix=self.prefix,
                filter_id=FILTER_ID,
                labels_rules=LABELS_RULES_STR,
                attrs_rules=ATTRS_RULES_STR))

        call_args = list(self.filters_client.create.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)
        self.assertEqual(call_args[0][1], LABELS_RULES_LIST + ATTRS_RULES_LIST)

    def test_create_filters_missing_filter_id(self):
        cmd = '{} create'.format(self.prefix)
        self._test_missing_argument(cmd, 'FILTER_ID')

    def test_create_filters_invalid_filter_rules(self):
        self._test_providing_invalid_filter_rules('create')

    def test_get_filters(self):
        cmd = '{0} get {1}'.format(self.prefix, FILTER_ID)
        self.filters_client.get = MagicMock()
        self.invoke(cmd)
        call_args = list(self.filters_client.get.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)

    def test_get_filters_missing_filter_id(self):
        self._test_missing_argument('{} get'.format(self.prefix), 'FILTER_ID')

    def test_filters_list(self):
        self.filters_client.list = MagicMock()
        self.invoke('{} list'.format(self.prefix))
        call_args = list(self.filters_client.list.call_args)
        self.assertEqual(call_args[1],
                         {'sort': 'id', 'is_descending': False,
                          '_all_tenants': False, '_search': None,
                          '_offset': 0, '_size': 1000})

    def test_filters_update(self):
        self.filters_client.update = MagicMock()
        cmd_with_filter_rules = \
            '{cmd_prefix} update {filter_id} --labels-rules "{labels_rules}"' \
            ' --attrs-rules "{attrs_rules}"'.format(
                cmd_prefix=self.prefix, filter_id=FILTER_ID,
                labels_rules=LABELS_RULES_STR,
                attrs_rules=ATTRS_RULES_STR)
        cmd_with_visibility = '{cmd_prefix} update {filter_id} --visibility ' \
                              'global'.format(cmd_prefix=self.prefix,
                                              filter_id=FILTER_ID)
        cmd_with_filter_rules_and_visibility = \
            cmd_with_filter_rules + ' --visibility global'

        self.invoke(cmd_with_filter_rules)
        call_args = list(self.filters_client.update.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)
        self.assertEqual(call_args[0][1], LABELS_RULES_LIST + ATTRS_RULES_LIST)
        self.assertEqual(call_args[0][2], None)

        self.invoke(cmd_with_visibility)
        call_args = list(self.filters_client.update.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)
        self.assertEqual(call_args[0][1], [])
        self.assertEqual(call_args[0][2], 'global')

        self.invoke(cmd_with_filter_rules_and_visibility)
        call_args = list(self.filters_client.update.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)
        self.assertEqual(call_args[0][1], LABELS_RULES_LIST + ATTRS_RULES_LIST)
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
        self.filters_client.delete = MagicMock()
        self.invoke('{0} delete {1}'.format(self.prefix, FILTER_ID))
        call_args = list(self.filters_client.delete.call_args)
        self.assertEqual(call_args[0][0], FILTER_ID)

    def test_delete_filters_missing_filter_id(self):
        self._test_missing_argument('{} delete'.format(self.prefix),
                                    'FILTER_ID')

    def test_list_with_filters(self):
        self.resource_client.list = MagicMock(
            return_value=MockListResponse()
        )
        self.invoke('cfy {resource} list --filter-id {filter_id} '
                    '--attrs-filter "{attrs_rules}" '
                    '--labels-filter "{labels_rules}"'.format(
                     resource=self.resource, filter_id=FILTER_ID,
                     attrs_rules=ATTRS_RULES_STR,
                     labels_rules=LABELS_RULES_STR))

        call_args = list(self.resource_client.list.call_args)
        call_args[1]['filter_rules'] = ATTRS_RULES_LIST + LABELS_RULES_LIST
        call_args[1]['filter_id'] = FILTER_ID

    def test_deployments_list_with_invalid_filters(self):
        self.invoke('cfy {} list --attrs-filter "e~1"'.format(self.resource),
                    err_str_segment='The attributes filter rule `e~1`',
                    exception=BadAttributesFilterRule)

        self.invoke('cfy {} list --labels-filter "e is"'.format(self.resource),
                    err_str_segment='The labels filter rule `e is`',
                    exception=BadLabelsFilterRule)

    def _test_missing_argument(self, command, argument):
        outcome = self.invoke(
            command,
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('missing argument', outcome.output.lower())
        self.assertIn(argument, outcome.output)

    def _test_providing_invalid_filter_rules(self, command):
        err_labels_rules = '"a=b and e is"'
        err_attrs_rules = '"a=b and c is"'
        err_labels_cmd = '{cmd_prefix} {command} --labels-rules ' \
                         '{labels_rules}'.format(cmd_prefix=self.prefix,
                                                 command=command,
                                                 labels_rules=err_labels_rules)
        err_attrs_cmd = '{cmd_prefix} {command} --attrs-rules ' \
                        '{attrs_rules}'.format(cmd_prefix=self.prefix,
                                               command=command,
                                               attrs_rules=err_attrs_rules)
        self.invoke(
            err_labels_cmd,
            err_str_segment='The labels filter rule `e is`',
            exception=BadLabelsFilterRule
        )

        self.invoke(
            err_attrs_cmd,
            err_str_segment='The attributes filter rule `c is`',
            exception=BadAttributesFilterRule
        )


class BlueprintsFiltersTest(FiltersTest):
    __test__ = True

    def setUp(self):
        super(BlueprintsFiltersTest, self).setUp('blueprints')


class DeploymentsFiltersTest(FiltersTest):
    __test__ = True

    def setUp(self):
        super(DeploymentsFiltersTest, self).setUp('deployments')
