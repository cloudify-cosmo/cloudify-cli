########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from .. import env
from ..cli import cfy
from ..exceptions import CloudifyCliError


def _verify_not_in_cluster(client):
    status = client.cluster.status()
    if status.initialized:
        raise CloudifyCliError('This manager machine is already part '
                               'of a HA cluster')


@cfy.group(name='cluster')
@cfy.options.verbose()
def cluster():
    """Handle the Manager HA Cluster
    """
    if not env.is_initialized():
        env.raise_uninitialized()


@cluster.command(name='status',
                 short_help='Show the current cluster status [cluster only]')
@cfy.pass_client()
@cfy.pass_logger
def status(client, logger):
    """Display the current status of the HA cluster
    """
    status = client.cluster.status()
    if not status.initialized:
        logger.error('This manager is not part of a Cloudify HA cluster')
    else:
        logger.info('HA cluster initialized!\nEncryption key: {0}'
                    .format(status.encryption_key))
