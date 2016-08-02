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
@cfy.argument('manager-ip')
@cfy.options.profile_alias
@cfy.options.manager_user
@cfy.options.manager_key
@cfy.options.manager_port
@cfy.options.rest_port
@cfy.options.verbose
@cfy.add_logger
def use(alias,
        manager_ip,
        manager_user,
        manager_key,
        manager_port,
        rest_port,
        logger):
    """Control a specific manager

    `MANAGEMENT_IP` is the IP of the manager to use.

    Additional CLI commands will be added after a manager is used.
    To stop using a manager, you can run `cfy init -r`.
    """
    # TODO: add support for setting the ssh port

    if manager_ip == 'local':
        logger.info('Using local environment...')
        if not env.is_profile_exists(manager_ip):
            init.init_profile(profile_name=manager_ip)
        env.set_active_profile('local')
        return

    logger.info('Attempting to connect...'.format(manager_ip))
    # determine SSL mode by port
    if rest_port == constants.SECURED_REST_PORT:
        rest_protocol = constants.SECURED_REST_PROTOCOL
    else:
        rest_protocol = constants.DEFAULT_REST_PROTOCOL
    client = env.get_rest_client(
        rest_host=manager_ip,
        rest_port=rest_port,
        rest_protocol=rest_protocol,
        skip_version_check=True)
    try:
        # first check this server is available.
        client.manager.get_status()
    except UserUnauthorizedError:
        raise CloudifyCliError(
            "Can't use manager {0}: User is unauthorized.".format(
                manager_ip))
    # TODO: Be more specific. The problem here is that, for instance,
    # any problem raised by the rest client will trigger this.
    # Triggering a CloudifyClientError only doesn't actually deal
    # with situations like No route to host and the likes.
    except Exception as ex:
        raise CloudifyCliError(
            "Can't use manager {0}: {1}".format(manager_ip, str(ex)))

    if not env.is_profile_exists(manager_ip):
        init.init_profile(profile_name=manager_ip)
    env.set_active_profile(manager_ip)
    if manager_ip == 'local':
        return

    try:
        response = client.manager.get_context()
        provider_context = response['context']
    except CloudifyClientError:
        provider_context = None

    logger.info('Using manager {0} with port {1}'.format(
        manager_ip, rest_port))

    with env.update_profile_context(manager_ip) as context:
        context.set_manager_ip(manager_ip)
        context.set_provider_context(provider_context)
        if manager_key:
            context.set_manager_key(manager_key)
        if manager_user:
            context.set_manager_user(manager_user)
        if manager_port:
            context.set_manager_port(manager_port)
        if rest_port:
            context.set_rest_port(rest_port)
        context.set_rest_protocol(rest_protocol)

    # delete the previous manager deployment if exists.
    bs.delete_workdir()
