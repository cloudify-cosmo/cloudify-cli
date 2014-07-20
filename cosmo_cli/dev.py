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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############


__author__ = 'dan'

import os
import sys

from fabric.api import env
from fabric.context_managers import settings


def execute(username, key, ip, task, tasks_file, args):
    _setup_fabric_env(username=username,
                      key=key)
    tasks_module = _import_tasks_module(tasks_file=tasks_file)
    _execute_task(ip=ip,
                  task=task,
                  tasks_module=tasks_module,
                  task_args=args)


def _setup_fabric_env(username, key):
    env.user = username
    env.key_filename = key
    env.warn_only = True
    env.abort_on_prompts = False
    env.connection_attempts = 5
    env.keepalive = 0
    env.linewise = False
    env.pool_size = 0
    env.skip_bad_hosts = False
    env.timeout = 10
    env.forward_agent = True
    env.status = False
    env.disable_known_hosts = False


def _import_tasks_module(tasks_file=None):
    if tasks_file:
        sys.path.append(os.path.dirname(tasks_file))
        tasks_module = __import__(os.path.basename(os.path.splitext(
            tasks_file)[0]))
    else:
        sys.path.append(os.getcwd())
        try:
            import tasks as tasks_module
        except ImportError:
            raise CosmoDevError('could not find a tasks file to import.'
                                ' either create a tasks.py file in your '
                                'cwd or use the --tasks-file flag to '
                                'point to one.')
    return tasks_module


def _execute_task(ip, task, tasks_module, task_args):
    task = task.replace('-', '_')
    args, kwargs = _parse_task_args(task_args)
    try:
        task_function = getattr(tasks_module, task)
    except AttributeError:
        raise CosmoDevError('task: "{0}" not found'.format(task))
    try:
        with settings(host_string=ip):
            task_function(*args, **kwargs)
    except Exception as e:
        raise CosmoDevError('failed to execute: "{0}" '
                            '({1}) '.format(task, str(e)))


def _parse_task_args(task_args):
    args = []
    kwargs = {}
    for task_arg in task_args:
        if task_arg.startswith('--'):
            task_arg = task_arg[2:]
            split = task_arg.split('=')
            key = split[0].replace('-', '_')
            if len(split) == 1:
                if key.startswith('no_'):
                    key = key[3:]
                    value = False
                else:
                    value = True
            else:
                value = ''.join(split[1:])
            kwargs[key] = value
        else:
            args.append(task_arg)
    return args, kwargs


class CosmoDevError(Exception):
    pass
