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
Handles 'cfy bootstrap'
"""

from cloudify_cli import provider_common
from cloudify_cli import utils
from cloudify_cli.bootstrap import bootstrap as bs
from cloudify_cli.logger import lgr


def bootstrap(config_file_path,
              keep_up,
              validate_only,
              skip_validations,
              blueprint_path,
              inputs=None):
    settings = utils.load_cloudify_working_dir_settings()
    if settings.get_is_provider_config():
        if blueprint_path or inputs:
            raise ValueError(
                'the "blueprint_path" and "inputs" parameters '
                'are not to be used with the deprecated provider API')
        return provider_common.provider_bootstrap(config_file_path,
                                                  keep_up,
                                                  validate_only,
                                                  skip_validations)
    details = bs.bootstrap(
        blueprint_path,
        name='manager',
        inputs=utils.json_to_dict(inputs, 'inputs'),
        task_retries=5,
        task_retry_interval=30,
        task_thread_pool_size=1)

    manager_ip = details['manager_ip']
    provider_name = details['provider_name']
    provider_context = details['provider_context']
    with utils.update_wd_settings() as ws_settings:
        ws_settings.set_management_server(manager_ip)
        ws_settings.set_management_key(details['manager_key_path'])
        ws_settings.set_management_user(details['manager_user'])
        ws_settings.set_provider(provider_name)
        ws_settings.set_provider_context(provider_context)

    lgr.info('bootstrapping complete')
    lgr.info('management server is up at {0}'.format(manager_ip))
