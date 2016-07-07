########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
# * See the License for the specific language governing permissions and
#    * limitations under the License.

import click

from .. import utils
from ..config import cfy
from ..logger import get_logger
from ..exceptions import CloudifyCliError


@cfy.group(name='profiles')
def profiles():
    """Handle Cloudify CLI profiles
    """
    pass


@profiles.command(name='init')
@click.argument('profile-name', required=True)
@cfy.options.management_ip
@cfy.options.management_user
@cfy.options.management_key
@cfy.options.management_password
@cfy.options.management_port
@cfy.options.rest_port
@cfy.options.show_active
@click.pass_context
def init(ctx,
         profile_name,
         management_ip,
         management_user,
         management_key,
         management_password,
         management_port,
         rest_port):
    """Initialize a new working profile
    """
    logger = get_logger()

    workdir = utils.CLOUDIFY_WORKDIR
    context_file_path = os.path.join(
        workdir, profile_name, constants.CLOUDIFY_WD_SETTINGS_FILE_NAME)

    if os.path.exists(context_file_path):
        raise CloudifyCliError(
            'Profile {0} already exists. Please delete it before initializing '
            'it by running `cfy profiles delete {0}`'.format(profile_name))
    else:
        logger.info('Creating profile {0}...'.format(profile_name))
        os.makedirs(context_file_path)

    settings = utils.CloudifyWorkingDirectorySettings()
    utils.dump_cloudify_working_dir_settings(settings)
    utils.dump_configuration_file()
    configure_loggers()

    if rest_port == constants.SECURED_REST_PORT:
        protocol = constants.SECURED_PROTOCOL
    else:
        protocol = constants.DEFAULT_PROTOCOL
    with utils.update_wd_settings() as wd_settings:
        if management_ip:
            wd_settings.set_management_server(management_ip)
            wd_settings.set_rest_port(rest_port)
            wd_settings.set_protocol(protocol)
            logger.info('Using manager {0} with port {1}'.format(
                management_ip, rest_port))
        if management_user:
            wd_settings.set_management_user(management_user)
            logger.info('Using SSH user vagrant'.format(management_user))
        if management_key:
            wd_settings.set_management_key(management_key)
            logger.info('Using SSH key-file {0}'.format(management_key))
        if management_password:
            wd_settings.set_management_password(management_password)
            logger.info('Using SSH password {0}'.format(management_password))
        if management_port:
            wd_settings.set_management_port(management_port)
            logger.info('Using SSH port {0}'.format(management_port))

    logger.info('Initialization completed successfully')
