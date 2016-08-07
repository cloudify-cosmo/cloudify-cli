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

from cloudify_rest_client.exceptions import  CloudifyClientError,\
    UserUnauthorizedError

from . import init
from .. import env
from ..cli import cfy
from .. import constants
from ..bootstrap import bootstrap as bs
from ..exceptions import CloudifyCliError


@cfy.command(name='use',
             short_help='Control a specific manager')
@cfy.argument('manager-ip')
# TODO: remove
@cfy.options.profile_alias
@cfy.options.manager_user
@cfy.options.manager_key
@cfy.options.manager_port
@cfy.options.rest_port
@cfy.options.verbose()
@cfy.pass_logger
# TODO: Shorten function
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
    # TODO: manager_ip -> profile_name
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
        # First check this server is available.
        client.manager.get_status()
    except UserUnauthorizedError:
        raise CloudifyCliError(
            "Can't use manager {0}: User is unauthorized.".format(
                manager_ip))
    # The problem here is that, for instance,
    # any problem raised by the rest client will trigger this.
    # Triggering a CloudifyClientError only doesn't actually deal
    # with situations like No route to host and the likes.
    except Exception as ex:
        raise CloudifyCliError(
            "Can't use manager {0}: {1}".format(manager_ip, str(ex)))

    if not env.is_profile_exists(manager_ip):
        init.init_profile(profile_name=manager_ip)
    env.set_active_profile(manager_ip)
    # TODO: Remove
    if manager_ip == 'local':
        return

    try:
        response = client.manager.get_context()
        provider_context = response['context']
    except CloudifyClientError:
        provider_context = None

    logger.info('Using manager {0} with port {1}'.format(
        manager_ip, rest_port))

    profile = env.profile
    profile.manager_ip = manager_ip
    profile.provider_context = provider_context
    if manager_key:
        profile.manager_key = manager_key
    if manager_user:
        profile.manager_user = manager_user
    if manager_port:
        profile.manager_port = manager_port
    if rest_port:
        profile.rest_port = rest_port
    profile.rest_protocol = rest_protocol

    profile.save()

    # delete the previous manager deployment if exists.
    bs.delete_workdir()
