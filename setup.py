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

from setuptools import setup


setup(
    name='cloudify',
    version='3.1a3',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    packages=['cosmo_cli', 'cloudify_simple_provider'],
    package_data={
        'cosmo_cli': ['VERSION'],
        'cloudify_simple_provider': ['cloudify-config.yaml',
                                     'cloudify-config.defaults.yaml']
    },
    license='LICENSE',
    description='Cloudify CLI',
    entry_points={
        'console_scripts': [
            'cfy = cosmo_cli.cosmo_cli:main',
            'activate_cfy_bash_completion = cosmo_cli.activate_bash_completion:main'  # NOQA
        ]
    },
    install_requires=[
        'cloudify-rest-client==3.1a3',
        'cloudify-dsl-parser==3.1a3',
        'pyyaml==3.10',
        'argcomplete==0.7.1',
        'fabric==1.8.3',
        'jsonschema==2.3.0',
        'PrettyTable>=0.7,<0.8'
    ]
)
