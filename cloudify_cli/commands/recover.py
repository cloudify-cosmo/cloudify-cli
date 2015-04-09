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

import os

from cloudify_cli import utils
from cloudify_cli import exceptions
from cloudify_cli.bootstrap import bootstrap as bs
from cloudify_cli.logger import get_logger


CLOUDIFY_MANAGER_PK_PATH_ENVAR = 'CLOUDIFY_MANAGER_PRIVATE_KEY_PATH'


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

    if CLOUDIFY_MANAGER_PK_PATH_ENVAR not in os.environ:
        if not os.path.isfile(os.path.expanduser(utils.get_management_key())):
            raise RuntimeError("Can't find manager private key file. Set the "
                               "path to it using the {0} environment variable"
                               .format(CLOUDIFY_MANAGER_PK_PATH_ENVAR))

    logger.info('Recovering manager deployment')
    settings = utils.load_cloudify_working_dir_settings()
    provider_context = settings.get_provider_context()
    bs.read_manager_deployment_dump_if_needed(
        provider_context.get('cloudify', {}).get('manager_deployment'))
    bs.recover(task_retries=task_retries,
               task_retry_interval=task_retry_interval,
               task_thread_pool_size=task_thread_pool_size)
    logger.info('Successfully recovered manager deployment')
