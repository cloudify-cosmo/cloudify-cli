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

import click
from fabric.api import env as fabric_env
from fabric.context_managers import settings

from ..env import profile
from ..cli import cfy, helptexts
from ..exceptions import CloudifyCliError


@cfy.command(name='dev', short_help='Run fabric tasks [manager only]')
@cfy.argument('task', required=True)
@click.option('-t',
              '--tasks-file',
              required=True,
              help='Tasks file from which to draw tasks')
@click.option('-a',
              '--args',
              multiple=True,
              help=helptexts.DEV_TASK_ARGS)
@cfy.options.verbose()
@cfy.assert_manager_active()
def dev(tasks_file, task, args):
    """Run fabric tasks on the manager
    """
    _execute(username=profile.ssh_user,
             port=profile.ssh_port,
             key=profile.ssh_key,
             ip=profile.manager_ip,
             task=task,
             tasks_file=tasks_file,
             args=args)


def _execute(username, port, key, ip, task, tasks_file, args):
    _setup_fabric_env(username=username, port=port, key=key)
    tasks = exec_tasks_file(tasks_file=tasks_file)
    _execute_task(ip=ip, task=task, tasks=tasks, task_args=args)


def _setup_fabric_env(username, port, key):
    fabric_env.user = username
    fabric_env.port = port
    fabric_env.key_filename = key
    fabric_env.warn_only = True
    fabric_env.abort_on_prompts = False
    fabric_env.connection_attempts = 5
    fabric_env.keepalive = 0
    fabric_env.linewise = False
    fabric_env.pool_size = 0
    fabric_env.skip_bad_hosts = False
    fabric_env.timeout = 10
    fabric_env.forward_agent = True
    fabric_env.status = False
    fabric_env.disable_known_hosts = False


def exec_tasks_file(tasks_file=None):
    tasks_file = tasks_file or 'tasks.py'
    exec_globals = get_exec_globals(tasks_file)
    try:
        execfile(tasks_file, exec_globals)
    except Exception as e:
        raise CloudifyCliError('Failed evaluating {0} ({1}:{2}'
                               .format(tasks_file, type(e).__name__, e))

    return dict([(task_name, task) for task_name, task in exec_globals.items()
                 if callable(task) and not task_name.startswith('_')])


def _execute_task(ip, task, tasks, task_args):
    task = task.replace('-', '_')
    args, kwargs = _parse_task_args(task_args)
    task_function = tasks.get(task)
    if not task_function:
        raise CloudifyCliError('Task {0} not found'.format(task))
    try:
        with settings(host_string=ip):
            task_function(*args, **kwargs)
    except Exception as e:
        raise CloudifyCliError('Failed to execute {0} ({1}) '.format(
            task, str(e)))


def _parse_task_args(task_args):
    task_args = task_args or []
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


def get_exec_globals(tasks_file):
    copied_globals = globals().copy()
    copied_globals.pop('exec_globals', None)
    copied_globals['__doc__'] = 'empty globals for exec'
    copied_globals['__file__'] = tasks_file
    copied_globals['__name__'] = 'cli_dev_tasks'
    copied_globals['__package__'] = None
    return copied_globals
