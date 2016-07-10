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

import click

from cloudify_rest_client.exceptions import (
    CloudifyClientError,
    UserUnauthorizedError
)

from . import init
from .. import utils
from .. import constants
from ..config import cfy
from ..logger import get_logger
from ..bootstrap import bootstrap as bs
from ..exceptions import CloudifyCliError


@cfy.command(name='use')
@click.argument('profile-name')
@cfy.options.management_ip
@cfy.options.management_user
@cfy.options.management_key
@cfy.options.management_password
@cfy.options.management_port
@cfy.options.rest_port
@cfy.options.show_active
@click.pass_context
def use(ctx,
        profile_name,
        management_ip,
        management_user,
        management_key,
        management_password,
        management_port,
        rest_port):
    """Control a specific manager

    Additional CLI commands will be added after a manager is used.
    To stop using a manager, you can run `cfy init -r`.
    """
    logger = get_logger()

    if profile_name in ('local', 'default'):
        if not utils.is_profile_exists(profile_name):
            ctx.invoke(init.init, profile_name=profile_name)
        if profile_name == 'local':
            utils.set_active_profile(profile_name)
            return

    utils.assert_profile_exists(profile_name)
    utils.set_active_profile(profile_name)

    if not (management_ip or
            management_user or
            management_key or
            management_password or
            management_port):
        # TODO: add this message to helptexts.py
        raise CloudifyCliError(
            'You must specify either `MANAGEMENT_IP` or the '
            '`--management-user` or `--management-key` flags')

    if management_ip:
        logger.info('Attemping to connect...'.format(management_ip))
        # determine SSL mode by port
        if rest_port == constants.SECURED_REST_PORT:
            protocol = constants.SECURED_PROTOCOL
        else:
            protocol = constants.DEFAULT_PROTOCOL
        client = utils.get_rest_client(
            manager_ip=management_ip,
            rest_port=rest_port,
            protocol=protocol,
            skip_version_check=True)
        try:
            # first check this server is available.
            client.manager.get_status()
        except UserUnauthorizedError:
            raise CloudifyCliError(
                "Can't use manager {0}: User is unauthorized.".format(
                    management_ip))
        except CloudifyClientError as e:
            raise CloudifyCliError(
                "Can't use manager {0}: {1}".format(management_ip, str(e)))

        try:
            response = client.manager.get_context()
            provider_context = response['context']
        except CloudifyClientError:
            provider_context = None

    with utils.update_wd_settings(profile_name) as wd_settings:
        if management_ip:
            wd_settings.set_management_server(management_ip)
            wd_settings.set_provider_context(provider_context)
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
    # delete the previous manager deployment if exists.
    bs.delete_workdir()
