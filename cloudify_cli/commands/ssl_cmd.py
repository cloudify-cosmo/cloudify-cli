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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

from ..cli import cfy
from .profiles import set_profile


@cfy.group(name='ssl')
@cfy.options.verbose()
@cfy.assert_manager_active()
def ssl():
    """Handle the manager's external ssl
    """
    pass


@ssl.command(name='status', short_help='Show SSL status')
@cfy.assert_manager_active()
@cfy.options.verbose()
@cfy.pass_client()
@cfy.pass_logger
def status(logger, client):
    """Show SSL status on the manager (enabled/disabled).
    """
    logger.info(client.manager.ssl_status())


@ssl.command(name='enable', short_help='Enables SSL [manager only]')
@cfy.assert_manager_active()
@cfy.options.verbose()
@cfy.pass_client()
@cfy.pass_logger
def enable(logger, client):
    """Enable SSL on the manager.
    """
    logger.info(client.manager.set_ssl(True))
    set_profile(profile_name=None,
                manager_username=None,
                manager_password=None,
                manager_tenant=None,
                ssh_user=None,
                ssh_key=None,
                ssh_port=None,
                ssl='on',
                rest_certificate=None,
                skip_credentials_validation=True,
                logger=logger)
    logger.info("Note that each user should now use SSL to communicate with "
                "the manager, they can do so by running:")
    logger.info("cfy profiles set --ssl on --skip-credentials-validation")


@ssl.command(name='disable', short_help='Disable SSL [manager only]')
@cfy.assert_manager_active()
@cfy.options.verbose()
@cfy.pass_client()
@cfy.pass_logger
def disable(logger, client):
    """Disable SSL on the manager.
    """
    logger.info(client.manager.set_ssl(False))
    set_profile(profile_name=None,
                manager_username=None,
                manager_password=None,
                manager_tenant=None,
                ssh_user=None,
                ssh_key=None,
                ssh_port=None,
                ssl='off',
                rest_certificate=None,
                skip_credentials_validation=True,
                logger=logger)
    logger.info("Note that each user should now communicate with the manager "
                "without SSL, they can do so by running:")
    logger.info("cfy profiles set --ssl off --skip-credentials-validation")
