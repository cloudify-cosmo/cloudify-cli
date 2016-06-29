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
from ..config import options
from ..logger import get_logger
from ..bootstrap import bootstrap as bs
from ..exceptions import CloudifyCliError


@click.command(name='use', context_settings=utils.CLICK_CONTEXT_SETTINGS)
@click.argument('management-ip', required=False)
@options.management_user
@options.management_key
@options.rest_port
@options.show_active
@click.pass_context
def use(ctx,
        management_ip,
        management_user,
        management_key,
        rest_port):
    """Control a specific manager

    Additional CLI commands will be added after a manager is used.
    To stop using a manager, you can run `cfy init -r`.
    """
    logger = get_logger()
    if not (management_ip or management_user or management_key):
        # TODO: add this message to I know where
        raise CloudifyCliError(
            'You must specify either `MANAGEMENT_IP` or the '
            '`--management-user` or `--management-key` flags')

    # TODO: remove this and allow multiple profile names instead.
    if management_ip == 'local':
        ctx.invoke(init.init, reset_config=True)
        return

    logger.info('Attemping to connect...'.format(management_ip))
    # determine SSL mode by port
    if rest_port == constants.SECURED_REST_PORT:
        protocol = constants.SECURED_PROTOCOL
    else:
        protocol = constants.DEFAULT_PROTOCOL
    client = utils.get_rest_client(
        manager_ip=management_ip, rest_port=rest_port, protocol=protocol,
        skip_version_check=True)
    try:
        # first check this server is available.
        client.manager.get_status()
    except UserUnauthorizedError:
        msg = "Can't use manager {0}: User is unauthorized.".format(
            management_ip)
        raise CloudifyCliError(msg)
    except CloudifyClientError as e:
        msg = "Can't use manager {0}: {1}".format(management_ip, str(e))
        raise CloudifyCliError(msg)

    # check if cloudify was initialized.
    if not utils.is_initialized():
        utils.dump_cloudify_working_dir_settings()
        utils.dump_configuration_file()

    try:
        response = client.manager.get_context()
        provider_context = response['context']
    except CloudifyClientError:
        provider_context = None

    with utils.update_wd_settings() as wd_settings:
        if management_ip:
            wd_settings.set_management_server(management_ip)
            wd_settings.set_provider_context(provider_context)
            wd_settings.set_rest_port(rest_port)
            wd_settings.set_protocol(protocol)
            logger.info('Using manager {0} with port {1}'.format(
                management_ip, rest_port))
        if management_user:
            wd_settings.set_management_user(management_user)
            logger.info('Using user vagrant'.format(management_user))
        if management_key:
            wd_settings.set_management_key(management_key)
            logger.info('Using key file {0}'.format(management_key))
    # delete the previous manager deployment if exists.
    bs.delete_workdir()
