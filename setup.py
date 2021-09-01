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

setup(
    name='cloudify',
    version='6.2.0',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=['cloudify_cli',
              'cloudify_cli.cli',
              'cloudify_cli.commands',
              'cloudify_cli.config'],
    package_data={
        'cloudify_cli': [
            'VERSION',
            'config/config_template.yaml',
        ],
    },
    license='LICENSE',
    description="Cloudify's Command Line Interface",
    entry_points={
        'console_scripts': [
            'cfy = cloudify_cli.main:_cfy'
        ]
    },
    install_requires=[
        'click>7,<8',
        'wagon[venv]>=0.10.1',
        'pyyaml==5.4.1',
        'jinja2>=2.10,<2.11',
        'retrying==1.3.3',
        'colorama==0.4.4',
        'requests>=2.7.0,<3.0.0',
        'click_didyoumean==0.0.3',
        'cloudify-common[dispatcher]==6.2.0',
        'backports.shutil_get_terminal_size==1.0.0',
        'ipaddress==1.0.23',
        'setuptools<=40.7.3',
        'cryptography==3.3.2',
        # Fabric depend on paramiko that depends on cryptography so we need
        # to install the correct version of cryptography before installing
        # the fabric so that fabric can be installed correctly in both py2 +
        # py3
        'fabric==2.5.0',
    ]
)
