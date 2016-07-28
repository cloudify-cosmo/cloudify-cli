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

from .. import env
from .. import exceptions
from ..config import cfy
from ..config import helptexts
from ..bootstrap import bootstrap as bs


CLOUDIFY_MANAGER_PK_PATH_ENVAR = 'CLOUDIFY_MANAGER_PRIVATE_KEY_PATH'


@cfy.command(name='recover',
             short_help='Recover a manager')
@cfy.argument('snapshot-path')
@cfy.options.force(help=helptexts.FORCE_RECOVER)
@cfy.options.task_retries()
@cfy.options.task_retry_interval()
@cfy.options.task_thread_pool_size()
@cfy.options.verbose
@cfy.add_logger
def recover(snapshot_path,
            force,
            task_retries,
            task_retry_interval,
            task_thread_pool_size,
            logger):
    """Recover a manager to a previous state

    `SNAPSHOT_PATH` is the path of the snapshot to use for recovery.
    """
    if not force:
        raise exceptions.CloudifyCliError(
            "This action requires additional "
            "confirmation. Add the '-f' or '--force' "
            "flags to your command if you are certain "
            "this command should be executed.")

    if CLOUDIFY_MANAGER_PK_PATH_ENVAR in os.environ:
        # user defined the key file path inside an env variable.
        # validate the existence of the keyfile because it will later be
        # used in a fabric task to ssh to the manager
        key_path = os.path.expanduser(os.environ[
            CLOUDIFY_MANAGER_PK_PATH_ENVAR])
        if not os.path.isfile(key_path):
            raise exceptions.CloudifyValidationError(
                "Cannot perform recovery. manager private key file "
                "defined in {0} environment variable does not "
                "exist: {1}".format(CLOUDIFY_MANAGER_PK_PATH_ENVAR, key_path)
            )
    else:
        # try retrieving the key file from the local context
        try:
            key_path = os.path.expanduser(env.get_management_key())
            if not os.path.isfile(key_path):
                # manager key file path exists in context but does not exist
                # in the file system. fail now.
                raise exceptions.CloudifyValidationError(
                    "Cannot perform recovery. manager key file does not "
                    "exist: {0}. Set the manager private key path via the {1} "
                    "environment variable"
                    .format(key_path, CLOUDIFY_MANAGER_PK_PATH_ENVAR)
                )
            # in this case, the recovery is executed from the same directory
            # that the bootstrap was executed from. we should not have
            # problems
        except exceptions.CloudifyCliError:
            # manager key file path does not exist in the context. this
            # means the recovery is executed from a different directory than
            # the bootstrap one. is this case the user must set the
            # environment variable to continue.
            raise exceptions.CloudifyValidationError(
                "Cannot perform recovery. manager key file not found. Set "
                "the manager private key path via the {0} environment "
                "variable".format(CLOUDIFY_MANAGER_PK_PATH_ENVAR)
            )

    logger.info('Recovering manager...')
    settings = env.get_profile_context()
    provider_context = settings.get_provider_context()
    bs.read_manager_deployment_dump_if_needed(
        provider_context.get('cloudify', {}).get('manager_deployment'))
    bs.recover(task_retries=task_retries,
               task_retry_interval=task_retry_interval,
               task_thread_pool_size=task_thread_pool_size,
               snapshot_path=snapshot_path)
    logger.info('Manager recovered successfully')
