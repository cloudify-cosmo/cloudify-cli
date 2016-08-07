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
@cfy.argument('profile-name')
@cfy.options.manager_user
@cfy.options.manager_key
@cfy.options.manager_port
@cfy.options.rest_port
@cfy.options.verbose()
@cfy.pass_logger
def use(profile_name,
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
    if profile_name == 'local':
        logger.info('Using local environment...')
        if not env.is_profile_exists(profile_name):
            init.init_local_profile()
        env.set_active_profile('local')
        return

    logger.info('Attempting to connect...'.format(profile_name))
    # determine SSL mode by port
    if rest_port == constants.SECURED_REST_PORT:
        rest_protocol = constants.SECURED_REST_PROTOCOL
    else:
        rest_protocol = constants.DEFAULT_REST_PROTOCOL

    if not env.is_profile_exists(profile_name):
        init.init_manager_profile(profile_name=profile_name)

    env.set_active_profile(profile_name)
    provider_context = _get_provider_context(
        profile_name,
        rest_port,
        rest_protocol
    )

    logger.info('Using manager {0} with port {1}'.format(
        profile_name, rest_port))

    _set_profile_context(
        profile_name,
        provider_context,
        manager_key,
        manager_user,
        manager_port,
        rest_port,
        rest_protocol
    )

    # delete the previous manager deployment if exists.
    bs.delete_workdir()


def _assert_manager_available(client, profile_name):
    try:
        client.manager.get_status()
    except UserUnauthorizedError:
        raise CloudifyCliError(
            "Can't use manager {0}: User is unauthorized.".format(
                profile_name))
    # The problem here is that, for instance,
    # any problem raised by the rest client will trigger this.
    # Triggering a CloudifyClientError only doesn't actually deal
    # with situations like No route to host and the likes.
    except Exception as ex:
        raise CloudifyCliError(
            "Can't use manager {0}: {1}".format(profile_name, str(ex)))


def _get_provider_context(profile_name, rest_port, rest_protocol):
    client = env.get_rest_client(
        rest_host=profile_name,
        rest_port=rest_port,
        rest_protocol=rest_protocol,
        skip_version_check=True)

    _assert_manager_available(client, profile_name)

    try:
        response = client.manager.get_context()
        return response['context']
    except CloudifyClientError:
        return None


def _set_profile_context(profile_name,
                         provider_context,
                         manager_key,
                         manager_user,
                         manager_port,
                         rest_port,
                         rest_protocol):
    profile = env.profile
    profile.manager_ip = profile_name
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