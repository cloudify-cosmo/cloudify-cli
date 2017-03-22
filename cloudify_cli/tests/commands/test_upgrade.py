# The upgrade command is temporary disabled
#
# from .test_base import BaseUpgradeTest
#
#
# class UpgradeTest(BaseUpgradeTest):
#
#     def setUp(self):
#         super(UpgradeTest, self).setUp()
#         self.use_manager()
#
#     def test_not_in_maintenance_upgrade(self):
#         self._test_not_in_maintenance(action='upgrade')
#
#     def test_upgrade_no_bp(self):
#         self._test_no_bp(action='upgrade')
#
#     def _test_upgrade_no_private_ip(self):
#         self._test_no_private_ip(action='upgrade')
#
#     def _test_upgrade_no_inputs(self):
#         self._test_no_inputs(action='upgrade')
