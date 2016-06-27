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
from ..logger import get_logger
from ..bootstrap import bootstrap as bs
from ..exceptions import CloudifyCliError
from ..constants import DEFAULT_REST_PORT


def show_active_manager(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    logger = get_logger()

    print_solution = False
    current_management_ip = utils.get_management_server_ip()
    try:
        current_management_user = utils.get_management_user()
    except CloudifyCliError as ex:
        print_solution = True
        current_management_user = str(ex)
    try:
        current_management_key = utils.get_management_key()
    except CloudifyCliError as ex:
        print_solution = True
        current_management_key = str(ex)
    logger.info('Management IP: {0}'.format(current_management_ip))
    logger.info('Management User: {0}'.format(current_management_user))
    logger.info('Management Key: {0}'.format(current_management_key))
    if print_solution:
        logger.info(
            'You can run the `-u` and `-k` flags to set the user and '
            'key-file path respectively. '
            '(e.g. `cfy use -u my_user -k ~/my/key/path`)'
        )
    ctx.exit()


@click.command(name='use', context_settings=utils.CLICK_CONTEXT_SETTINGS)
@click.argument('management-ip', required=False)
@click.option('-u',
              '--management-user',
              required=False,
              help="The username on the host "
              "machine with which you bootstrapped")
@click.option('-k',
              '--management-key',
              required=False,
              help="The path to the ssh key-file you used to bootstrap")
@click.option('--rest-port',
              required=False,
              default=DEFAULT_REST_PORT,
              help="The REST server's port")
@click.option('--show-active',
              is_flag=True,
              is_eager=True,
              expose_value=False,
              callback=show_active_manager,
              help="Show connection information for the active manager")
def use(management_ip,
        management_user,
        management_key,
        rest_port):
    """Control a specific manager

    Additional CLI commands will be added after a manager is used.
    To stop using a manager, you can run `cfy init -r`.
    """
    logger = get_logger()

    if not management_ip or management_user or management_key:
        raise CloudifyCliError(
            'You must specify either `MANAGEMENT_IP` or the '
            '`--management-user` or `--management-key` flags')

    # TODO: remove this and allow multiple profile names instead.
    if management_ip == 'local':
        init.init(reset_config=True)
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
