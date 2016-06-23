from .test_base import BaseUpgradeTest


class RollbackTest(BaseUpgradeTest):

    def setUp(self):
        super(RollbackTest, self).setUp()
        self.use_manager()

    def test_not_in_maintenance_rollback(self):
        self._test_not_in_maintenance(action='rollback')

    def test_rollback_no_bp(self):
        self._test_no_bp(action='rollback')

    def test_rollback_no_private_ip(self):
        self._test_no_private_ip(action='rollback')

    def test_rollback_no_inputs(self):
        self._test_no_inputs(action='rollback')
