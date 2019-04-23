########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

import os

from cloudify_cli.cli import cfy
from cloudify_cli.table import print_data
from cloudify_cli.exceptions import CloudifyValidationError

LICENSE_COLUMN = ['customer_id', 'expiration_date', 'license_edition', 'trial',
                  'cloudify_version', 'capabilities', 'expired']


@cfy.group(name='license')
@cfy.options.common_options
@cfy.assert_manager_active()
def license():
    """ Handle Cloudify licenses
    """
    pass


@license.command(
    name='list',
    short_help='Get the Cloudify license that was uploaded to this Manager')
@cfy.assert_manager_active()
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def list(logger, client):
    """Returns the Cloudify license from the Manager.
    """
    logger.info('Retrieving Cloudify License')
    license = client.license.list()
    print_data(LICENSE_COLUMN, license, 'Cloudify License')


@license.command(
    name='upload',
    short_help='Upload a new Cloudify license to the Manager')
@cfy.argument('license-path')
@cfy.assert_manager_active()
@cfy.options.common_options
@cfy.pass_client()
@cfy.pass_logger
def upload(logger, client, license_path):
    logger.info('Uploading Cloudify License `{0}` to the Manager...'.
                format(license_path))
    if not os.path.isfile(license_path):
        raise CloudifyValidationError('License file was not found in the '
                                      'following path: `{0}`'.
                                      format(license_path))
    client.license.upload(license_path)
    logger.info('Cloudify license successfully uploaded.')
