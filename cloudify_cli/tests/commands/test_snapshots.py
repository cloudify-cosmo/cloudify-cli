########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from mock import MagicMock

from cloudify_rest_client.snapshots import Snapshot
from cloudify_rest_client.executions import Execution

from cloudify_cli.tests.commands.test_cli_command import SNAPSHOTS_DIR
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class SnapshotsTest(CliCommandTest):

    def setUp(self):
        super(SnapshotsTest, self).setUp()
        self.use_manager()

    def test_snapshots_list(self):
        self.client.snapshots.list = MagicMock(return_value=[])
        self.invoke('cfy snapshots list')

    def test_snapshots_delete(self):
        self.client.snapshots.delete = MagicMock()
        self.invoke('cfy snapshots delete a-snapshot-id')

    def test_snapshots_upload(self):
        self.client.snapshots.upload = MagicMock(
            return_value=Snapshot({'id': 'some_id'}))
        self.invoke('cfy snapshots upload {0}/snapshot.zip '
                    '-s my_snapshot_id'.format(SNAPSHOTS_DIR))

    def test_snapshots_create(self):
        self.client.snapshots.create = MagicMock(
            return_value=Execution({'id': 'some_id'}))
        self.invoke('cfy snapshots create a-snapshot-id')

    def test_snapshots_restore(self):
        self.client.snapshots.restore = MagicMock()
        self.invoke('cfy snapshots restore a-snapshot-id')
        self.invoke('cfy snapshots restore a-snapshot-id'
                    '--without-deployments-envs')

    def test_snapshots_download(self):
        self.client.snapshots.download = MagicMock(return_value='some_file')
        self.invoke('cfy snapshots download a-snapshot-id')
