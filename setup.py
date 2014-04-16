########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'ran'

from setuptools import setup

VERSION = '3.0'

REST_CLIENT_VERSION = '3.0'
REST_CLIENT_BRANCH = 'develop'
REST_CLIENT = 'https://github.com/cloudify-cosmo/cloudify-rest-client' \
              '/tarball/{0}#egg=cloudify-rest-client-{1}'.format(
                  REST_CLIENT_BRANCH, REST_CLIENT_VERSION)

DSL_PARSER_VERSION = '3.0'
DSL_PARSER_BRANCH = 'develop'
DSL_PARSER = 'https://github.com/cloudify-cosmo/cloudify-dsl-parser/tarball/' \
             '{0}#egg=cloudify-dsl-parser-{1}'.format(
                 DSL_PARSER_BRANCH, DSL_PARSER_VERSION)


setup(
    name='cloudify-cli',
    version=VERSION,
    author='ran',
    author_email='ran@gigaspaces.com',
    packages=['cosmo_cli'],
    license='LICENSE',
    description='Cloudify CLI',
    entry_points={
        'console_scripts': [
            'cfy = cosmo_cli.cosmo_cli:main',
            'activate_cfy_bash_completion = cosmo_cli.activate_bash_completion:main'  # NOQA
        ]
    },
    install_requires=[
        'pyyaml==3.10',
        'cloudify-rest-client',
        'cloudify-dsl-parser',
        'argcomplete==0.7.1',
        "scp==0.7.2",
        "fabric==1.8.3",
        "jsonschema==2.3.0",
    ],
    dependency_links=[REST_CLIENT, DSL_PARSER]
)
