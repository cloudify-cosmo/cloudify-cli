########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from cloudify_rest_client.exceptions import (
    CloudifyClientError,
    UserUnauthorizedError
)

from .. import env
from .. import utils
from .. import common
from ..config import cfy
from ..logger import get_logger


@cfy.command(name='status')
@cfy.options.verbose
def status():
    """Show the status of the manager
    """
    logger = get_logger()
    management_ip = env.get_management_server_ip()
    client = env.get_rest_client(management_ip)

    if not env.is_manager_active():
        logger.info(
            'No manager is currently being used. You can either '
            'bootstrap a manager or run `cfy use` to use an existing one.')
        return

    logger.info('Retrieving manager services status... [ip={0}]'.format(
        management_ip))

    try:
        status_result = client.manager.get_status()
        maintenance_response = client.maintenance_mode.status()
    except UserUnauthorizedError:
        logger.info(
            "Failed to query manager servicetatus: User is unauthorized")
        return False
    except CloudifyClientError:
        logger.info('REST service at manager {0} is not responding!'.format(
            management_ip))
        return False

    services = []
    for service in status_result['services']:
        state = service['instances'][0]['state'] \
            if 'instances' in service and \
               len(service['instances']) > 0 else 'unknown'
        services.append({
            'service': service['display_name'].ljust(30),
            'status': state
        })
    pt = utils.table(['service', 'status'], data=services)
    common.print_table('Services:', pt)

    maintenance_status = maintenance_response.status
    if maintenance_status != 'deactivated':
        logger.info('Maintenance mode is {0}.\n'.format(
            maintenance_response.status))
    return True
