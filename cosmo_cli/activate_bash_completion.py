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

import platform
import subprocess
import getpass
from os.path import expanduser

__author__ = 'nir'


def main():
    if platform.dist()[0] in ('Ubuntu', 'Debian'):
        print 'identified distro {0}'.format(platform.dist()[0])

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
        else:
            print 'autocomplete already installed'
        try:
            print 'attempting to source ~/.bashrc'
            execfile('{0}/.bashrc'.format(home))
            print 'cfy bash completion is now active in your shell'
        except:
            print 'failed to source ~/.bashrc'
            print 'reload your shell or run ". ~/.bashrc"'
    if platform.dist()[0] == 'Windows':
        return 0
    if platform.dist()[0] == 'CentOS':
        return 0
    if platform.dist()[0] == 'openSUSE':
        return 0

if __name__ == '__main__':
    main()
