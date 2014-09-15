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
Handles 'cfy bootstrap'
"""

import os

from cloudify_cli.exceptions import CloudifyCliError, CloudifyValidationError
from cloudify_cli.exceptions import CloudifyBootstrapError
from cloudify_cli.logger import lgr
from cloudify_cli import cli
from cloudify_cli import utils
from cloudify_cli import provider_common


def bootstrap(config_file_path, keep_up, validate_only, skip_validations):
    provider_name = utils.get_provider()
    provider = utils.get_provider_module(provider_name)
    try:
        provider_dir = provider.__path__[0]
    except:
        provider_dir = os.path.dirname(provider.__file__)
    provider_config = utils.read_config(config_file_path,
                                        provider_dir)
    lgr.info("Prefix for all resources: '{0}'"
             .format(provider_config.resources_prefix))
    pm = provider.ProviderManager(provider_config, cli.get_global_verbosity())
    pm.keep_up_on_failure = keep_up

    if skip_validations and validate_only:
        raise CloudifyCliError('Please choose one of skip-validations or '
                               'validate-only flags, not both.')
    lgr.info('Bootstrapping using {0}'.format(provider_name))
    if skip_validations:
        pm.update_names_in_config()  # Prefixes
    else:
        lgr.info('Validating provider resources and configuration')
        pm.augment_schema_with_common()
        if pm.validate_schema():
            raise CloudifyValidationError('Provider schema '
                                          'validations failed!')
        pm.update_names_in_config()  # Prefixes
        if pm.validate():
            raise CloudifyValidationError('Provider validations failed!')
        lgr.info('Provider validations completed successfully')

    if validate_only:
        return
    with utils.protected_provider_call():
        lgr.info('Provisioning resources for management server...')
        params = pm.provision()

    installed = False
    provider_context = {}

    def keep_up_or_teardown():
        if keep_up:
            lgr.info('topology will remain up')
        else:
            lgr.info('tearing down topology'
                     ' due to bootstrap failure')
            pm.teardown(provider_context)

    if params:
        mgmt_ip, private_ip, ssh_key, ssh_user, provider_context = params
        lgr.info('provisioning complete')
        lgr.info('ensuring connectivity with the management server...')
        if pm.ensure_connectivity_with_management_server(
                mgmt_ip, ssh_key, ssh_user):
            lgr.info('connected with the management server successfully')
            lgr.info('bootstrapping the management server...')
            try:
                installed = pm.bootstrap(mgmt_ip, private_ip, ssh_key,
                                         ssh_user)
            except BaseException:
                lgr.error('bootstrapping failed!')
                keep_up_or_teardown()
                raise
            lgr.info('bootstrapping complete') if installed else \
                lgr.error('bootstrapping failed!')
        else:
            lgr.error('failed connecting to the management server!')
    else:
        lgr.error('provisioning failed!')

    if installed:
        provider_common._update_provider_context(provider_config,
                                                 provider_context)

        mgmt_ip = mgmt_ip.encode('utf-8')

        with utils.update_wd_settings() as wd_settings:
            wd_settings.set_management_server(mgmt_ip)
            wd_settings.set_management_key(ssh_key)
            wd_settings.set_management_user(ssh_user)
            wd_settings.set_provider_context(provider_context)

        # storing provider context on management server
        utils.get_rest_client(mgmt_ip).manager.create_context(provider_name,
                                                              provider_context)

        lgr.info('management server is up at {0} '
                 '(is now set as the default management server)'
                 .format(mgmt_ip))
    else:
        keep_up_or_teardown()
        raise CloudifyBootstrapError()


