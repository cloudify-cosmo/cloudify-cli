########
# Copyright (c) 2018 GigaSpaces Technologies Ltd. All rights reserved
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

from ..cli import cfy
from ..table import print_single

REST_TOKEN_COLUMN = ['role', 'value']


@cfy.group(name='tokens')
@cfy.assert_manager_active()
def tokens():
    """ Returns a valid REST token from the Cloudify Manager
    """
    pass


@tokens.command(
    name='get',
    short_help='returns a valid REST token from the Cloudify Manager')
@cfy.assert_manager_active()
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def get(logger, client):
    """returns a valid REST token from the Cloudify Manager.
    """
    logger.info('Retrieving REST token')
    token = client.tokens.get()
    print_single(REST_TOKEN_COLUMN, token, 'REST token')
