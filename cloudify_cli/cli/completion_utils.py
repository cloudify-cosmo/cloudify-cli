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

from argcomplete.completers import FilesCompleter

from .. import env
from ..commands import dev

yaml_files_completer = FilesCompleter(['*.yml', '*.yaml'])
archive_files_completer = FilesCompleter(
    ['*.zip', '*.tar', '*.tar.gz', '*.tar.bz2'])


def objects_args_completer_maker(objects_type, **kw):
    def _objects_args_completer(prefix, **kwargs):
        context = env.get_profile_context(
            suppress_error=True)
        if not context:
            return []

        rest_client = env.get_rest_client()
        objs_ids_list = getattr(rest_client, objects_type).list(
            _include=['id'])
        return (obj.id for obj in objs_ids_list if obj.id.startswith(prefix))
    return _objects_args_completer


def workflow_id_completer(prefix, parsed_args, **kwargs):
    # TODO: refactor this into '_objects_args_completer_maker' method once
    #       workflows get their own module in rest-client
    if not parsed_args.deployment_id:
        return []

    context = env.get_profile_context(
        suppress_error=True)
    if not context:
        return []

    rest_client = env.get_rest_client()

    deployment_id = parsed_args.deployment_id
    workflows = rest_client.deployments.get(
        deployment_id, _include=['workflows']).workflows
    return (wf.id for wf in workflows if wf.id.startswith(prefix))


def dev_task_name_completer(prefix, parsed_args, **kwargs):
    tasks_file = parsed_args.tasks_file or 'tasks.py'
    try:
        tasks = dev.exec_tasks_file(tasks_file)
    except Exception:
        return []
    return (task_name.replace('_', '-') for task_name in tasks.keys())
