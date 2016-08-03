########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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


# TODO: Check what this is used for an consolidate

def exec_globals(tasks_file):
    copied_globals = globals().copy()
    del copied_globals['exec_globals']
    copied_globals['__doc__'] = 'empty globals for exec'
    copied_globals['__file__'] = tasks_file
    copied_globals['__name__'] = 'cli_dev_tasks'
    copied_globals['__package__'] = None
    return copied_globals
