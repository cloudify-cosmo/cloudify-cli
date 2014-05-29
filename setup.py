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
from pip.req import parse_requirements

install_requires = [
    str(ir.req) for ir in parse_requirements('requirements.txt')]


setup(
    name='cloudify-cli',
    version=3.0,
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
    install_requires=install_requires
)
