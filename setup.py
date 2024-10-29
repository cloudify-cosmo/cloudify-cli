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

from setuptools import setup

install_requires = [
    'backports.shutil_get_terminal_size',
    'click',
    'click_didyoumean',
    'cloudify-common[dispatcher]',
    'colorama',
    'cryptography==43.0.1',
    'fabric',
    'requests>=2.32.0,<3',
    'retrying',
    'wagon[venv]',
]

packages = [
    'cloudify_cli',
    'cloudify_cli.cli',
    'cloudify_cli.commands',
    'cloudify_cli.config',
    'cloudify_cli.async_commands',
]

setup(
    name='cloudify',
    version='7.0.5',
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
    install_requires=install_requires,
)
