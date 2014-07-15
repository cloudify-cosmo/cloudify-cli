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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############


from cosmo_cli.provider_common import BaseProviderClass


class ProviderManager(BaseProviderClass):

    def provision(self):
        properties = ['public_ip',
                      'private_ip',
                      'ssh_key_path',
                      'ssh_username',
                      'context']
        return tuple([self._get_property(prop) for prop in properties])

    def _get_property(self, name):
        value = self.provider_config.get(name)
        if value is None:
            raise ValueError('Missing value for property: "{}" in '
                             'configuration '.format(name))
        return value

    def teardown(self, provider_context, ignore_validation=False):
        pass

    def validate(self):
        pass
