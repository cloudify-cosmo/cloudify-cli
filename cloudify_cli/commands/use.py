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

from cloudify_rest_client.exceptions import (
    CloudifyClientError,
    UserUnauthorizedError
)

from .. import env
from .. import constants
from ..config import cfy
from ..bootstrap import bootstrap as bs
from ..exceptions import CloudifyCliError

from . import init


@cfy.command(name='use',
             short_help='Control a specific manager')
@cfy.argument('management-ip')
@cfy.options.profile_alias
@cfy.options.management_user
@cfy.options.management_key
@cfy.options.management_password
@cfy.options.management_port
@cfy.options.rest_port
@cfy.options.verbose
@cfy.add_logger
def use(alias,
        management_ip,
        management_user,
        management_key,
        management_password,
        management_port,
        rest_port,
        logger):
    """Control a specific manager

    `MANAGEMENT_IP` is the IP of the manager to use.

    Additional CLI commands will be added after a manager is used.
    To stop using a manager, you can run `cfy init -r`.
    """
    # TODO: add support for setting the ssh port and password

    management_ip = management_ip or 'local'
    if management_ip == 'local':
        logger.info('Using local environment...')
        if not env.is_profile_exists(management_ip):
            init.init_profile(profile_name=management_ip)
        env.set_active_profile('local')
        return

    logger.info('Attempting to connect...'.format(management_ip))
    # determine SSL mode by port
    if rest_port == constants.SECURED_REST_PORT:
        rest_protocol = constants.SECURED_REST_PROTOCOL
    else:
        rest_protocol = constants.DEFAULT_REST_PROTOCOL
    client = env.get_rest_client(
        rest_host=management_ip,
        rest_port=rest_port,
        rest_protocol=rest_protocol,
        skip_version_check=True)
    try:
        # first check this server is available.
        client.manager.get_status()
    except UserUnauthorizedError:
        raise CloudifyCliError(
            "Can't use manager {0}: User is unauthorized.".format(
                management_ip))
    # TODO: Be more specific. The problem here is that, for instance,
    # any problem raised by the rest client will trigger this.
    # Triggering a CloudifyClientError only doesn't actually deal
    # with situations like No route to host and the likes.
    except Exception as e:
        raise CloudifyCliError(
            "Can't use manager {0}: {1}".format(management_ip, str(e)))

    if not env.is_profile_exists(management_ip):
        init.init_profile(profile_name=management_ip)
    env.set_active_profile(management_ip)
    if management_ip == 'local':
        return

    try:
        response = client.manager.get_context()
        provider_context = response['context']
    except CloudifyClientError:
        provider_context = None

    with env.update_wd_settings(management_ip) as wd_settings:
        wd_settings.set_management_server(management_ip)
        wd_settings.set_provider_context(provider_context)
        wd_settings.set_rest_port(rest_port)
        wd_settings.set_rest_protocol(rest_protocol)
        logger.info('Using manager {0} with port {1}'.format(
            management_ip, rest_port))
        if management_user:
            wd_settings.set_management_user(management_user)
        if management_key:
            wd_settings.set_management_key(management_key)
        if management_password:
            wd_settings.set_management_password(management_password)
        if management_port:
            wd_settings.set_management_port(management_port)
    # delete the previous manager deployment if exists.
    bs.delete_workdir()
