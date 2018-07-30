########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import sys
import shutil
import tarfile
import logging
import subprocess

from uuid import uuid4
from functools import wraps
from StringIO import StringIO
from datetime import datetime
from contextlib import contextmanager

from mock import patch

from cloudify_cli.constants import DEFAULT_TENANT_NAME

import cloudify.utils
import cloudify.exceptions
from cloudify import ctx as op_ctx
from cloudify.decorators import operation, workflow
from cloudify.state import workflow_ctx as workflow_ctx
from cloudify.workflows import tasks as workflow_tasks

from cloudify_rest_client.nodes import Node
from cloudify_rest_client.executions import Execution
from cloudify_rest_client.maintenance import Maintenance
from cloudify_rest_client.node_instances import NodeInstance


def mock_fabric_sudo(command, *args, **kwargs):
    subprocess.check_call(command.split(' '))


def mock_fabric_put(local_path, remote_path, *args, **kwargs):
    shutil.copy(local_path, remote_path)


def execution_mock(status, wf_id='mock_wf'):
    return Execution({
        'status': status,
        'workflow_id': wf_id,
        'deployment_id': 'deployment-id',
        'blueprint_id': 'blueprint-id',
        'error': '',
        'id': uuid4(),
        'created_at': datetime.now().isoformat()[:-3],
        'parameters': {
            'param1': 'value1'
        },
        'visibility': 'private',
        'created_by': 'admin',
        'tenant_name': DEFAULT_TENANT_NAME
    })


def mock_log_message_prefix(event):
    return event['event_name']


@operation
def mock_op(param, custom_param=None, **kwargs):
    props = op_ctx.instance.runtime_properties
    props['param'] = param
    props['custom_param'] = custom_param
    props['provider_context'] = op_ctx.provider_context


@workflow
def mock_workflow(param, custom_param=None, **kwargs):
    for node in workflow_ctx.nodes:
        for instance in node.instances:
            instance.execute_operation('test.op', kwargs={
                'param': param,
                'custom_param': custom_param
            })


@workflow
def logging_workflow(**kwargs):
    kwargs.pop('ctx', None)
    graph = workflow_ctx.graph_mode()
    instance = next(workflow_ctx.node_instances)
    task = instance.execute_operation('test.op', kwargs=kwargs)

    def on_failure(tsk):
        return workflow_tasks.HandlerResult.ignore()
    task.on_failure = on_failure
    graph.add_task(task)
    graph.execute()


@operation
def logging_operation(level, message, error=False, user_cause=False, **kwargs):
    if error:
        causes = []
        if user_cause:
            try:
                raise RuntimeError(message)
            except RuntimeError:
                _, ex, tb = sys.exc_info()
                causes.append(cloudify.utils.exception_to_error_cause(
                    ex, tb))
        raise cloudify.exceptions.NonRecoverableError(message, causes=causes)
    else:
        level = getattr(logging, level)
        op_ctx.logger.log(level, message)


def counter(func):
    @wraps(func)
    def tmp(*_):
        tmp.count += 1
        return func()
    tmp.count = 0
    return tmp


@counter
def mock_activated_status():
    if mock_activated_status.count % 2 == 1:
        return Maintenance({'status': 'deactivated'})
    return Maintenance({'status': 'activated'})


def mock_is_timeout(*_):
    return True


def node_instance_get_mock():
    return NodeInstance({
        'id': uuid4(),
        'deployment_id': 'deployment_id',
        'host_id': 'host_id',
        'node_id': 'node_id',
        'state': 'started',
        'runtime_properties': {
            'floating_ip': '127.0.0.1'
        },
        'visibility': 'private',
        'created_by': 'admin',
        'tenant_name': DEFAULT_TENANT_NAME
    })


def node_get_mock():
    return Node({
        'id': uuid4(),
        'deployment_id': 'deployment-id',
        'blueprint_id': 'blueprint_id',
        'host_id': 'host_id',
        'type': 'Compute',
        'number_of_instances': '1',
        'planned_number_of_instances': '2',
        'properties': {
            'port': '8080'
        },
        'visibility': 'private',
        'created_by': 'admin',
        'tenant_name': DEFAULT_TENANT_NAME
    })


def make_tarfile(output_filename, source_dir, write_type='w'):
    with tarfile.open(output_filename, write_type) as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


@contextmanager
def mock_stdout():
    stdout = StringIO()
    with patch('sys.stdout', stdout):
        yield stdout


class MockPagination(dict):
    def __init__(self, total=0):
        self.total = total


class MockMetadata(dict):
    def __init__(self, pagination=MockPagination()):
        self.pagination = pagination


class MockListResponse(object):
    def __init__(self, items=[], _=None):
        self.items = items
        self.metadata = MockMetadata()

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, index):
        return self.items[index]

    def __len__(self):
        return len(self.items)

    def sort(self, cmp=None, key=None, reverse=False):
        return self.items.sort(cmp, key, reverse)
