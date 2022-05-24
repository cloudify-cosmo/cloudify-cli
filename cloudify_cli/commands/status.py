########
# Copyright (c) 2014-2019 Cloudify Platform Ltd. All rights reserved
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

import json

from cloudify_rest_client.exceptions import CloudifyClientError, \
    UserUnauthorizedError

from cloudify_cli.cli import cfy
from cloudify_cli.env import profile
from cloudify_cli.logger import (
    CloudifyJSONEncoder,
    output,
    get_global_json_output)
from cloudify_cli.table import print_data

STATUS_COLUMNS = ['service', 'status']


@cfy.command(name='status', short_help="Show manager status [manager only]")
@cfy.options.common_options
@cfy.assert_manager_active()
@cfy.pass_client()
@cfy.pass_logger
def status(logger, client):
    """Show the status of the manager"""
    rest_host = profile.manager_ip
    logger.info('Retrieving manager services status... [ip={0}]'.format(
        rest_host))
    try:
        status_result = client.manager.get_status()
        maintenance_response = client.maintenance_mode.status()
    except UserUnauthorizedError:
        logger.info(
            'Failed to query manager service status: User is unauthorized')
        return False
    except CloudifyClientError:
        logger.info('REST service at manager {0} is not responding!'.format(
            rest_host))
        return False

    if get_global_json_output():
        output(json.dumps(status_result, cls=CloudifyJSONEncoder))
    else:
        services = []
        for display_name, service in status_result['services'].items():
            services.append({
                'service': display_name.ljust(30),
                'status': service.get('status')
            })
        print_data(STATUS_COLUMNS, services, 'Services:')

    maintenance_status = maintenance_response.status
    if maintenance_status != 'deactivated':
        logger.info('Maintenance mode is {0}.\n'.format(
            maintenance_response.status))
    return True
