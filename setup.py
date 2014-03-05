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

# activate venv
# pip install argcomplete
# eval "$(register-python-argcomplete cfy)"
# echo 'eval "$(register-python-argcomplete cfy)"' >> ~/.bashrc

__author__ = 'ran'

from setuptools import setup
from setuptools.command.install import install
from distutils.command.install import install as _install

version = '0.3'

COSMO_MANAGER_REST_CLIENT_VERSION = '0.3'
COSMO_MANAGER_REST_CLIENT_BRANCH = 'develop'
COSMO_MANAGER_REST_CLIENT = \
    "https://github.com/CloudifySource/cosmo-manager-rest-client/tarball/{" \
    "0}#egg=cosmo-manager-rest-client-{1}".format(
        COSMO_MANAGER_REST_CLIENT_BRANCH, COSMO_MANAGER_REST_CLIENT_VERSION)

COSMO_PLUGIN_DSL_PARSER_VERSION = '0.3'
COSMO_PLUGIN_DSL_PARSER_BRANCH = 'develop'
COSMO_PLUGIN_DSL_PARSER = \
    "https://github.com/CloudifySource/cosmo-plugin-dsl-parser/tarball/{" \
    "0}#egg=cosmo-plugin-dsl-parser-{1}".format(
        COSMO_PLUGIN_DSL_PARSER_BRANCH, COSMO_PLUGIN_DSL_PARSER_VERSION)


class CliAdvancedInstallation(install):
    def run(self):
        _install.run(self)

        import platform
        import subprocess
        import getpass
        from os.path import expanduser

        if platform.dist()[0] in ('Ubuntu', 'Debian'):
            user = getpass.getuser()
            home = expanduser("~")

            print 'adding bash completion for user {0}'.format(user)
            cmd_check_if_registered = ('grep "register-python-argcomplete '
                                       'cfy" {0}/.bashrc')
            x = subprocess.Popen(cmd_check_if_registered.format(home),
                                 shell=True,
                                 stdout=subprocess.PIPE)
            output = x.communicate()[0]
            if output == '':
                print 'adding autocomplete to ~/.bashrc'
                cmd_register_to_bash = ('''echo 'eval "$(register-python-argcomplete cfy)"' >> {0}/.bashrc''')  # NOQA
                subprocess.Popen(cmd_register_to_bash.format(home),
                                 shell=True,
                                 stdout=subprocess.PIPE)
                try:
                    print 'attempting to source bashrc'
                    execfile('{0}/.bashrc'.format(home))
                except:
                    print 'could not source bashrc'
                print 'if cfy autocomplete doesn\'t work, reload your shell or run ". ~/.bashrc'  # NOQA
            else:
                print 'autocomplete already installed'
        if platform.dist()[0] == 'Windows':
            return 0
        if platform.dist()[0] == 'CentOS':
            return 0
        if platform.dist()[0] == 'openSUSE':
            return 0

setup(
    name='cosmo-cli',
    version=version,
    author='ran',
    author_email='ran@gigaspaces.com',
    packages=['cosmo_cli'],
    license='LICENSE',
    description='the cosmo cli',
    entry_points={
        'console_scripts': ['cfy = cosmo_cli.cosmo_cli:main']
    },
    install_requires=[
        "pyyaml",
        "cosmo-manager-rest-client",
        "cosmo-plugin-dsl-parser",
        "argcomplete",
        # "fabric"
    ],
    dependency_links=[COSMO_MANAGER_REST_CLIENT, COSMO_PLUGIN_DSL_PARSER],
    cmdclass=dict(install=CliAdvancedInstallation)
)

# setup(
#     name='cosmo-cli',
#     version=version,
#     author='ran',
#     author_email='ran@gigaspaces.com',
#     packages=['cosmo_cli'],
#     license='LICENSE',
#     description='the cosmo cli',
#     cmdclass=dict(install=CliAdvancedInstallation)
# )
