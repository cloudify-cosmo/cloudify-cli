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

import os

from cloudify_cli.logger import lgr
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.cli import get_global_verbosity
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_cli import utils


def _get_provider_name_and_context(mgmt_ip):
    # trying to retrieve provider context from server
    try:
        response = utils.get_rest_client(mgmt_ip).manager.get_context()
        return response['name'], response['context']
    except CloudifyClientError as e:
        lgr.warn('Failed to get provider context from server: {0}'.format(
            str(e)))

    # using the local provider context instead (if it's relevant for the
    # target server)
    cosmo_wd_settings = utils.load_cloudify_working_dir_settings()
    if cosmo_wd_settings.get_provider_context():
        default_mgmt_server_ip = cosmo_wd_settings.get_management_server()
        if default_mgmt_server_ip == mgmt_ip:
            provider_name = utils.get_provider()
            return provider_name, cosmo_wd_settings.get_provider_context()
        else:
            # the local provider context data is for a different server
            msg = "Failed to get provider context from target server"
    else:
        msg = "Provider context is not set in working directory settings (" \
              "The provider is used during the bootstrap and teardown " \
              "process. This probably means that the manager was started " \
              "manually, without the bootstrap command therefore calling " \
              "teardown is not supported)."
    raise RuntimeError(msg)


def teardown(force, ignore_deployments, config_file_path, ignore_validation):
    management_ip = utils.get_management_server_ip()
    if not force:
        msg = ("This action requires additional "
               "confirmation. Add the '-f' or '--force' "
               "flags to your command if you are certain "
               "this command should be executed.")
        raise CloudifyCliError(msg)

    client = utils.get_rest_client(management_ip)
    if not ignore_deployments and len(client.deployments.list()) > 0:
        msg = ("Management server {0} has active deployments. Add the "
               "'--ignore-deployments' flag to your command to ignore "
               "these deployments and execute topology teardown."
               .format(management_ip))
        raise CloudifyCliError(msg)

    provider_name, provider_context = \
        _get_provider_name_and_context(management_ip)
    provider = utils.get_provider_module(provider_name)
    try:
        provider_dir = provider.__path__[0]
    except:
        provider_dir = os.path.dirname(provider.__file__)
    provider_config = utils.read_config(config_file_path,
                                        provider_dir)
    pm = provider.ProviderManager(provider_config, get_global_verbosity())

    lgr.info("tearing down {0}".format(management_ip))
    with utils.protected_provider_call():
        pm.teardown(provider_context, ignore_validation)

    # cleaning relevant data from working directory settings
    with utils.update_wd_settings() as wd_settings:
        # wd_settings.set_provider_context(provider_context)
        wd_settings.remove_management_server_context()

    lgr.info("teardown complete")
