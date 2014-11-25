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
    version='3.1',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    packages=['cloudify_cli',
              'cloudify_cli.commands',
              'cloudify_cli.bootstrap',
              'cloudify_cli.config'],
    package_data={
        'cloudify_cli': ['VERSION', 'resources/config.yaml'],
    },
    license='LICENSE',
    description='Cloudify CLI',
    entry_points={
        'console_scripts': [
            'cfy = cloudify_cli.cli:main',
            'activate_cfy_bash_completion = cloudify_cli.activate_bash_completion:main'  # NOQA
        ]
    },
    install_requires=[
        'cloudify-plugins-common==3.1',
        'cloudify-rest-client==3.1',
        'cloudify-dsl-parser==3.1',
        'cloudify-script-plugin==1.1',
        'pyyaml==3.10',
        'argcomplete==0.7.1',
        'fabric==1.8.3',
        'jsonschema==2.3.0',
        'PrettyTable>=0.7,<0.8',
        'ansicolors==1.0.2',
        'jinja2==2.7.2'
    ]
)
