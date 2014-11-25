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
from cloudify_cli import exceptions
from cloudify_cli.bootstrap import bootstrap as bs
from cloudify_cli.logger import get_logger


def teardown(force, ignore_deployments, config_file_path, ignore_validation):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    if not force:
        msg = ("This action requires additional "
               "confirmation. Add the '-f' or '--force' "
               "flags to your command if you are certain "
               "this command should be executed.")
        raise exceptions.CloudifyCliError(msg)

    client = utils.get_rest_client(management_ip)
    if not ignore_deployments and len(client.deployments.list()) > 0:
        msg = ("Management server {0} has active deployments. Add the "
               "'--ignore-deployments' flag to your command to ignore "
               "these deployments and execute topology teardown."
               .format(management_ip))
        raise exceptions.CloudifyCliError(msg)

    settings = utils.load_cloudify_working_dir_settings()
    if settings.get_is_provider_config():
        provider_common.provider_teardown(config_file_path, ignore_validation)
    else:
        logger.info("tearing down {0}".format(management_ip))
        provider_context = settings.get_provider_context()
        bs.read_manager_deployment_dump_if_needed(
            provider_context.get('cloudify', {}).get('manager_deployment'))
        bs.teardown(name='manager',
                    task_retries=0,
                    task_retry_interval=0,
                    task_thread_pool_size=1)

    # cleaning relevant data from working directory settings
    with utils.update_wd_settings() as wd_settings:
        # wd_settings.set_provider_context(provider_context)
        wd_settings.remove_management_server_context()

    logger.info("teardown complete")
