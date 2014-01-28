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

__author__ = 'ran'

import os


def init(target_dir, reset_config):
    config_file_path = os.path.join(target_dir, 'cloudify-config.yaml')
    if not reset_config and os.path.exists(config_file_path):
        return False
    open(config_file_path, 'a').close()
    return True


def bootstrap(config_path=None):
    return '10.0.0.2'


def teardown(management_ip):
    raise RuntimeError('cloudify_mock_provider2 teardown exception')
