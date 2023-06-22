########
# Copyright (c) 2013-2020 Cloudify Platform Ltd. All rights reserved
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
import sys

from setuptools import setup

install_requires = [
        'click>8,<9',
        'wagon[venv]>=0.11.2',
        'retrying==1.3.3',
        'colorama==0.4.4',
        'requests>=2.7.0,<3.0.0',
        'click_didyoumean==0.3.0',
        'cloudify-common[dispatcher]==7.0.1',
        'backports.shutil_get_terminal_size==1.0.0',
        'cryptography>=37,<40',
        'fabric==2.7.1',
]

packages = ['cloudify_cli',
            'cloudify_cli.cli',
            'cloudify_cli.commands',
            'cloudify_cli.config',
            'cloudify_cli.async_commands']

setup(
    name='cloudify',
    version='7.0.1',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=packages,
    license='LICENSE',
    description="Cloudify's Command Line Interface",
    entry_points={
        'console_scripts': [
            'cfy = cloudify_cli.main:_cfy'
        ]
    },
    install_requires=install_requires
)
