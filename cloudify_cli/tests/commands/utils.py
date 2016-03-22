########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from contextlib import contextmanager
from StringIO import StringIO

from mock import patch


@contextmanager
def mock_stdout():
    stdout = StringIO()
    with patch('sys.stdout', stdout):
        yield stdout


@contextmanager
def mock_logger(attribute_path):
    output = StringIO()

    class MockLogger(object):
        @staticmethod
        def info(message):
            output.write(message)
    with patch(attribute_path, MockLogger):
        yield output
