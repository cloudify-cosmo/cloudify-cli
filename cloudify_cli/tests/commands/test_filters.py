from mock import MagicMock

from cloudify_cli.cli.cfy import parse_filter_rules_list
from cloudify_cli.exceptions import CloudifyValidationError, CloudifyCliError

from .test_base import CliCommandTest


class FiltersTest(CliCommandTest):
    def setUp(self):
        super(FiltersTest, self).setUp()
        self.use_manager()

    def test_create_filters(self):
        self.client.filters.create = MagicMock()
        self.invoke('cfy filters create filter a=b')
        self.invoke('cfy filters create filter "a=b and c is null"')

    def test_create_filters_missing_filter_id(self):
        self._test_missing_argument('cfy filters create', 'FILTER_ID')

    def test_create_filters_missing_filter_rules(self):
        self._test_missing_argument(
            'cfy filters create filter', 'FILTER_RULES')

    def test_create_filters_invalid_filter_rules(self):
        self.invoke(
            'cfy filters create filter "a=b and e is"',
            err_str_segment='Filter rules must be one of',
            exception=CloudifyValidationError
        )

    def test_get_filters(self):
        self.client.filters.get = MagicMock()
        self.invoke('cfy filters get filter')

    def test_get_filters_missing_filter_id(self):
        self._test_missing_argument('cfy filters get', 'FILTER_ID')

    def test_filters_list(self):
        self.client.filters.list = MagicMock()
        self.invoke('cfy filters list')

    def test_filters_update(self):
        self.client.filters.update = MagicMock()
        self.invoke('cfy filters update filter --filter-rules a=b')
        self.invoke('cfy filters update filter --visibility global')
        self.invoke('cfy filters update filter --visibility global '
                    '--filter-rules a=b')

    def test_filters_update_invalid_filter_rules(self):
        self.invoke(
            'cfy filters update filter --filter-rules "a=b and e is"',
            err_str_segment='Filter rules must be one of',
            exception=CloudifyValidationError
        )

    def test_filters_update_invalid_visibility(self):
        self.invoke(
            'cfy filters update filter --visibility bla',
            err_str_segment='Invalid visibility: `bla`',
            exception=CloudifyCliError
        )

    def test_filters_delete(self):
        self.client.filters.delete = MagicMock()
        self.invoke('cfy filters delete filter')

    def test_delete_filters_missing_filter_id(self):
        self._test_missing_argument('cfy filters delete', 'FILTER_ID')

    def test_parse_filter_rules_list(self):
        filter_rules_str = 'a=b and c=[d,e] and f!=G   and h!=[i, J] and K ' \
                           'is null and l is not null'
        filter_rules_list = ['a=b', 'c=[d,e]', 'f!=g', 'h!=[i, j]',
                             'k is null', 'l is not null']
        self.assertEqual(
            filter_rules_list, parse_filter_rules_list(filter_rules_str))

    def _test_missing_argument(self, command, argument):
        outcome = self.invoke(
            command,
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('missing argument', outcome.output.lower())
        self.assertIn(argument, outcome.output)
