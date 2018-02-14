from collections import namedtuple

from .mocks import MockListResponse
from .test_base import CliCommandTest


class ListSortTest(CliCommandTest):
    _resource = namedtuple('Resource', 'name,class_type,sort_order,context')

    def setUp(self):
        super(ListSortTest, self).setUp()
        self.use_manager()
        self.resources = [
            ListSortTest._resource(
                'plugins',
                self.client.plugins,
                'uploaded_at',
                None
            ),
            ListSortTest._resource(
                'deployments',
                self.client.deployments,
                'created_at',
                None
            ),
            ListSortTest._resource(
                'nodes',
                self.client.nodes,
                'deployment_id',
                None
            ),
            ListSortTest._resource(
                'node-instances',
                self.client.node_instances,
                'node_id',
                'manager'
            ),
            ListSortTest._resource(
                'blueprints',
                self.client.blueprints,
                'created_at',
                None
            ),
            ListSortTest._resource(
                'snapshots',
                self.client.snapshots,
                'created_at',
                None
            ),
            ListSortTest._resource(
                'executions',
                self.client.executions,
                'created_at',
                None
            ),
            ListSortTest._resource(
                'users',
                self.client.users,
                'username',
                None
            ),
            ListSortTest._resource(
                'user-groups',
                self.client.user_groups,
                'name',
                None
            ),
        ]

        self.count_mock_calls = 0

        self.original_lists = {}
        for r in self.resources:
            self.original_lists[r.name] = r.class_type.list

    def tearDown(self):
        for r in self.resources:
            r.class_type.list = self.original_lists[r.name]
        super(ListSortTest, self).tearDown()

    def test_list_sort(self):
        for r in self.resources:
            self._set_mock_list(r, 'order')
            self.invoke(
                'cfy {0} list --sort-by order'
                .format(r.name), context=r.context
            )
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_reverse(self):
        for r in self.resources:
            self._set_mock_list(r, 'order', descending=True)
            self.invoke(
                'cfy {0} list --sort-by order --descending'
                .format(r.name), context=r.context
            )
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_default(self):
        for r in self.resources:
            self._set_mock_list(r, r.sort_order)
            self.invoke('cfy {0} list'.format(r.name), context=r.context)
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_default_reverse(self):
        for r in self.resources:
            self._set_mock_list(r, r.sort_order, descending=True)
            self.invoke('cfy {0} list --descending'
                        .format(r.name), context=r.context)
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def _set_mock_list(self, resource, sort, descending=False):
        def _mock_list(*_, **kwargs):
            self.count_mock_calls += 1
            self.assertEqual(sort, kwargs['sort'])
            self.assertEqual(descending, kwargs['is_descending'])
            return MockListResponse()

        resource.class_type.list = _mock_list
