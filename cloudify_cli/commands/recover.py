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
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from cloudify_cli import utils
from cloudify_cli import exceptions
from cloudify_cli.bootstrap import bootstrap as bs
from cloudify_cli.logger import get_logger


def recover(force,
            task_retries,
            task_retry_interval,
            task_thread_pool_size):
    logger = get_logger()
    if not force:
        msg = ("This action requires additional "
               "confirmation. Add the '-f' or '--force' "
               "flags to your command if you are certain "
               "this command should be executed.")
        raise exceptions.CloudifyCliError(msg)

    logger.info('Recovering manager deployment')
    settings = utils.load_cloudify_working_dir_settings()
    provider_context = settings.get_provider_context()
    bs.read_manager_deployment_dump_if_needed(
        provider_context.get('cloudify', {}).get('manager_deployment'))
    bs.recover(task_retries=task_retries,
               task_retry_interval=task_retry_interval,
               task_thread_pool_size=task_thread_pool_size)
    logger.info('Successfully recovered manager deployment')
