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

"""
Handles 'cfy teardown'
"""

from cloudify_cli import provider_common
from cloudify_cli import utils
from cloudify_cli.bootstrap import bootstrap as bs


def teardown(force, ignore_deployments, config_file_path, ignore_validation):
    settings = utils.load_cloudify_working_dir_settings()
    if settings.get_is_provider_config():
        return provider_common.provider_teardown(force,
                                                 ignore_deployments,
                                                 config_file_path,
                                                 ignore_validation)

    bs.teardown(name='manager',
                task_retries=0,
                task_retry_interval=0,
                task_thread_pool_size=1)
