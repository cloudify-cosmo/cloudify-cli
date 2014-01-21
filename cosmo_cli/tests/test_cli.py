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
from cosmo_cli import cosmo_cli
from cosmo_cli.cosmo_cli import CosmoCliError

__author__ = 'barakme'

import unittest


class CliTest(unittest.TestCase):


    def test_validate_blueprint_missing_file(self):
        input = ["cosmo_cli.py", "validate", "/path/to/no/such/file"]
        args = cosmo_cli.parse_args(input[1:])
        try:
            args.handler(args)
            self.fail("Expected file not found error")
        except CosmoCliError as e:
            self.assertTrue("Could not file file" in e.message)



    def test_validate_helloworld_blueprint(self):
        input = ["cosmo_cli.py", "validate", "helloworld/blueprint.yaml"]
        args = cosmo_cli.parse_args(input[1:])
        args.handler(args)


if __name__ == '__main__':
    unittest.main()