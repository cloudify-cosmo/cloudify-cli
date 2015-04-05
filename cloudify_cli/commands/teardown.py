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

"""
Handles 'cfy teardown'
"""

from cloudify_cli import utils
from cloudify_cli import exceptions
from cloudify_cli.bootstrap import bootstrap as bs
from cloudify_cli.logger import get_logger
from cloudify_cli.commands.use import use


def teardown(force, ignore_deployments):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    if not force:
        msg = ("This action requires additional "
               "confirmation. Add the '-f' or '--force' "
               "flags to your command if you are certain "
               "this command should be executed.")
        raise exceptions.CloudifyCliError(msg)

    client = utils.get_rest_client(management_ip)
    try:
        if not ignore_deployments and len(client.deployments.list()) > 0:
            msg = \
                ("Manager server {0} has existing deployments. Delete all "
                 "deployments first or add the '--ignore-deployments' flag to "
                 "your command to ignore these deployments and execute "
                 "teardown.".format(management_ip))
            raise exceptions.CloudifyCliError(msg)
    except IOError:
        msg = \
            "Failed querying manager server {0} about existing " \
            "deployments; The Manager server may be down. If you wish to " \
            'skip this check, you may use the "--ignore-deployments" flag, ' \
            'in which case teardown will occur regardless of the Manager ' \
            "server's status.".format(management_ip)
        raise exceptions.CloudifyCliError(msg)

    logger.info("tearing down {0}".format(management_ip))

    # runtime properties might have changed since the last time we
    # executed 'use', because of recovery. so we need to retrieve
    # the provider context again
    try:
        logger.info('Retrieving provider context')
        management_ip = utils.get_management_server_ip()
        use(management_ip, utils.get_rest_port())
    except BaseException as e:
        logger.warning('Failed retrieving provider context: {0}. This '
                       'may cause a leaking management server '
                       'in case it has gone through a '
                       'recovery process'.format(str(e)))

    # reload settings since the provider context maybe changed
    settings = utils.load_cloudify_working_dir_settings()
    provider_context = settings.get_provider_context()
    bs.read_manager_deployment_dump_if_needed(
        provider_context.get('cloudify', {}).get('manager_deployment'))
    bs.teardown()

    # cleaning relevant data from working directory settings
    with utils.update_wd_settings() as wd_settings:
        # wd_settings.set_provider_context(provider_context)
        wd_settings.remove_management_server_context()

    logger.info("teardown complete")
