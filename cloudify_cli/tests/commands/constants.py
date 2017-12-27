########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os

from cloudify_cli.constants import DEFAULT_BLUEPRINT_FILE_NAME


STUB_TIMEOUT = 900
STUB_FORCE = False
STUB_INCLUDE_LOGS = False
STUB_WORKFLOW = 'my_workflow'
STUB_PARAMETERS = 'key=value'
STUB_BLUEPRINT_ID = 'blueprint_id'
STUB_DIRECTORY_NAME = 'helloworld'
STUB_DEPLOYMENT_ID = 'deployment_id'
STUB_ALLOW_CUSTOM_PARAMETERS = False
STUB_ARCHIVE_LOCATION = 'archive.zip'
STUB_BLUEPRINT_FILENAME = 'my_blueprint.yaml'
SSL_PORT = '443'
THIS_DIR = os.path.dirname(os.path.dirname(__file__))
BLUEPRINTS_DIR = os.path.join(THIS_DIR, 'resources', 'blueprints')
SNAPSHOTS_DIR = os.path.join(THIS_DIR, 'resources', 'snapshots')
PLUGINS_DIR = os.path.join(THIS_DIR, 'resources', 'plugins')
SAMPLE_INPUTS_PATH = os.path.join(
    BLUEPRINTS_DIR, STUB_DIRECTORY_NAME, 'inputs.yaml')
SAMPLE_BLUEPRINT_PATH = os.path.join(
    BLUEPRINTS_DIR, STUB_DIRECTORY_NAME, DEFAULT_BLUEPRINT_FILE_NAME)
SAMPLE_ARCHIVE_URL = 'https://github.com/cloudify-cosmo/' \
                     'cloudify-hello-world-example/archive/master.zip'
SAMPLE_ARCHIVE_PATH = os.path.join(BLUEPRINTS_DIR, 'helloworld.zip')
SAMPLE_CUSTOM_NAME_ARCHIVE = os.path.join(
    BLUEPRINTS_DIR,
    'helloworld_custom_name.zip'
)
