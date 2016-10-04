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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

from testtools import TestCase
from testtools.matchers import Equals

from mock import (
    mock_open,
    patch,
)
from requests.exceptions import ConnectionError

from ..exceptions import CloudifyCliError
from ..utils import download_file


class DownloadFileTest(TestCase):

    """Download file test cases."""

    def setUp(self):
        """Initialize mock objects."""
        super(DownloadFileTest, self).setUp()

        self.expected_destination = '<filename>'

        tempfile_patcher = patch('cloudify_cli.utils.tempfile')
        tempfile = tempfile_patcher.start()
        tempfile.mkstemp.side_effect = [('<fd>', self.expected_destination)]
        self.addCleanup(tempfile_patcher.stop)

        os_patcher = patch('cloudify_cli.utils.os')
        os_patcher.start()
        self.addCleanup(os_patcher.stop)

        get_patcher = patch('cloudify_cli.utils.requests.get')
        self.get = get_patcher.start()
        self.addCleanup(get_patcher.stop)

        open_patcher = patch(
            'cloudify_cli.utils.open', mock_open(), create=True)
        self.open = open_patcher.start()
        self.addCleanup(open_patcher.stop)

        # Disable logger output when running test cases
        logger_patcher = patch('cloudify_cli.utils.get_logger')
        self.logger = logger_patcher.start()
        self.addCleanup(logger_patcher.stop)

    def test_download_success(self):
        """Download file successfully."""
        destination = download_file('some_url')
        self.assertThat(destination, Equals(self.expected_destination))

    def test_download_connection_error(self):
        """CloudifyCliError is raised on ConnectionError."""
        self.get.side_effect = ConnectionError
        self.assertRaises(CloudifyCliError, download_file, 'some_url')

    def test_download_ioerror(self):
        """CloudifyCliError is raised on IOError."""
        self.get().iter_content.return_value = ['<content>']
        self.open().__enter__().write.side_effect = IOError
        self.assertRaises(CloudifyCliError, download_file, 'some_url')
