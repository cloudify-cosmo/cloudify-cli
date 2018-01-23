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
    version='4.3.dev1',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
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
        'click==4.0',
        'wagon[venv]==0.6.1',
        'pyyaml==3.10',
        'paramiko==1.18.3',
        'fabric==1.13.1',
        'jinja2==2.7.2',
        'retrying==1.3.3',
        'colorama==0.3.3',
        'requests[security]>=2.7.0,<3.0.0',
        'PrettyTable>=0.7,<0.8',
        'click_didyoumean==0.0.3',
        'cloudify-dsl-parser==4.3.dev1',
        'cloudify-script-plugin==1.5.2',
        'cloudify-rest-client==4.3.dev1',
        'cloudify-plugins-common==4.3.dev1',
        'backports.shutil_get_terminal_size==1.0.0',

        # included from requests[security] because 9.0.1
        # pip install -r can't handle that properly
        "asn1crypto==0.24.",
        "cffi==1.11.",
        "cryptography==2.1.",
        "enum34==1.1.",
        "ipaddress==1.0.1",
        "pyOpenSSL==17.5.",
        "pycparser==2.18",
    ]
)
