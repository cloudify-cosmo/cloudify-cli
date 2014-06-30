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
import json


def find_version():
    with open('VERSION', 'rb') as ver_file:
        return json.load(ver_file)['version']

setup(
    name='cloudify-cli',
    version=find_version(),
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
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
        'cloudify-rest-client==3.0',
        'cloudify-dsl-parser==3.0',
        'pyyaml==3.10',
        'argcomplete==0.7.1',
        'fabric==1.8.3',
        'jsonschema==2.3.0',
    ],
    classifiers=[],
)
