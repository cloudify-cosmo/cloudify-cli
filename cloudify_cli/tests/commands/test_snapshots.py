from mock import MagicMock

from .constants import SNAPSHOTS_DIR
from .test_base import CliCommandTest

from cloudify_rest_client import snapshots, executions


class FakeExecutionReturn():
    def __init__(self, status):
        self.status = status
        self.error = None


class SnapshotsTest(CliCommandTest):

    def setUp(self):
        super(SnapshotsTest, self).setUp()
        self.use_manager()

    def test_snapshots_list(self):
        self.client.snapshots.list = MagicMock(return_value=[])
        self.invoke('cfy snapshots list')
        self.invoke('cfy snapshots list -t dummy_tenant')
        self.invoke('cfy snapshots list -a')

    def test_snapshots_delete(self):
        self.client.snapshots.delete = MagicMock()
        self.invoke('cfy snapshots delete a-snapshot-id')

    def test_snapshots_upload(self):
        self.client.snapshots.upload = MagicMock(
            return_value=snapshots.Snapshot({'id': 'some_id'}))
        self.invoke('cfy snapshots upload {0}/snapshot.zip '
                    '-s my_snapshot_id'.format(SNAPSHOTS_DIR))

    def test_snapshots_create(self):
        self.client.snapshots.create = MagicMock(
            return_value=executions.Execution({'id': 'some_id'}))
        self.invoke('cfy snapshots create a-snapshot-id')

    def test_snapshots_restore(self):
        self.client.snapshots.restore = MagicMock()
        self.client.snapshots._restore_deployment_environments = MagicMock()
        self.client.executions.get = MagicMock()
        self.client.executions.get.return_value = FakeExecutionReturn(
            'terminated',
        )
        self.client.tenants.list = MagicMock()
        self.client.tenants.list.return_value = []
        self.invoke('cfy snapshots restore a-snapshot-id')
        self.invoke('cfy snapshots restore a-snapshot-id'
                    '--without-deployments-envs')

    def test_snapshots_download(self):
        self.client.snapshots.download = MagicMock(return_value='some_file')
        self.invoke('cfy snapshots download a-snapshot-id')
