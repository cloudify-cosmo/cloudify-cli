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
Handles 'cfy use'
"""

from cloudify_cli.logger import get_logger
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_cli import utils


def use(management_ip, provider, rest_port):
    logger = get_logger()
    # first check this server is available.
    client = utils.get_rest_client(
        manager_ip=management_ip,
        rest_port=rest_port)
    try:
        status_result = client.manager.get_status()
    except CloudifyClientError:
        status_result = None
    if not status_result:
        msg = ("Can't use management server {0}: No response."
               .format(management_ip))
        raise CloudifyCliError(msg)

    # check if cloudify was initialized.
    if not utils.is_initialized():
        utils.dump_cloudify_working_dir_settings()
        utils.dump_configuration_file()

    try:
        response = utils.get_rest_client(
            management_ip).manager.get_context()
        provider_name = response['name']
        provider_context = response['context']
    except CloudifyClientError:
        provider_name = None
        provider_context = None

    with utils.update_wd_settings() as wd_settings:
        wd_settings.set_management_server(management_ip)
        wd_settings.set_provider_context(provider_context)
        wd_settings.set_provider(provider_name)
        wd_settings.set_rest_port(rest_port)
        wd_settings.set_is_provider_config(provider)
        logger.info('Using management server {0} with port {1}'
                    .format(management_ip, rest_port))
