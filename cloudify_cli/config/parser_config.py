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
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
#    * limitations under the License.

# flake8: noqa

import argparse

from cloudify_cli import commands as cfy
from cloudify_cli.config import completion_utils
from cloudify_cli.config import argument_utils
from cloudify_cli.constants import DEFAULT_REST_PORT

FORMAT_INPUT_AS_YAML_OR_DICT = 'formatted as YAML or as "key1=value1;key2=value2"'


def blueprint_id_argument():
    return {
        'metavar': 'BLUEPRINT_ID',
        'type': str,
        'help': 'The id of the blueprint',
        'dest': 'blueprint_id',
        'default': None,
        'required': True,
        'completer': completion_utils.objects_args_completer_maker('blueprints')
    }


def snapshot_id_argument(hlp):
    return {
        'metavar': 'SNAPSHOT_ID',
        'type': str,
        'help': hlp,
        'dest': 'snapshot_id',
        'default': None,
        'required': True,
        'completer': completion_utils.objects_args_completer_maker('snapshots')
    }


def deployment_id_argument(hlp):
    return {
        'dest': 'deployment_id',
        'metavar': 'DEPLOYMENT_ID',
        'type': str,
        'required': False,
        'help': hlp,
        'completer': completion_utils.objects_args_completer_maker('deployments')
    }


def execution_id_argument(hlp):
    return {
        'dest': 'execution_id',
        'metavar': 'EXECUTION_ID',
        'type': str,
        'required': True,
        'help': hlp,
        'completer': completion_utils.objects_args_completer_maker('executions')
    }


def workflow_id_argument(hlp):
    return {
        'metavar': 'WORKFLOW',
        'dest': 'workflow_id',
        'type': str,
        'required': True,
        'help': hlp,
        'completer': completion_utils.workflow_id_completer
    }


def plugin_id_argument(hlp):
    return {
        'metavar': 'PLUGIN_ID',
        'type': str,
        'help': hlp,
        'dest': 'plugin_id',
        'default': None,
        'required': True,
        'completer': completion_utils.objects_args_completer_maker('plugins')
    }


def parser_config():
    return {
        'description': 'Manages Cloudify in different Cloud Environments',
        'arguments': {
            '--version': {
                'help': 'show version information and exit',
                'action': cfy.version
            }
        },
        'commands': {
            'plugins': {
                'help': "Manages Cloudify's plugins",
                'sub_commands': {
                    'upload': {
                        'arguments': {
                            '-p,--plugin-path': {
                                'metavar': 'PLUGIN_FILE',
                                'dest': 'plugin_path',
                                'type': argparse.FileType(),
                                'required': True,
                                'help': 'Path to the plugin file',
                                'completer': completion_utils.yaml_files_completer
                            }
                        },
                        'help': 'command for uploading a plugin to the management server',
                        'handler': cfy.plugins.upload
                    },
                    'get': {
                        'arguments': {
                            '-p,--plugin-id': plugin_id_argument(
                                hlp='The plugin id')
                        },
                        'help': 'Command for listing all modules according to their plugin id',
                        'handler': cfy.plugins.get
                    },
                    'download': {
                        'arguments': {
                            '-p,--plugin-id': plugin_id_argument(
                                hlp='The plugin id'),
                            '-o,--output': {
                                'metavar': 'OUTPUT',
                                'type': str,
                                'help': 'The output file path of the plugin to be downloaded',
                                'dest': 'output',
                                'required': False
                            }
                        },
                        'help': 'Command for downloading a plugin from the management server',
                        'handler': cfy.plugins.download
                    },
                    'list': {
                        'help': 'Command for listing all plugins on the '
                                'Manager',
                        'handler': cfy.plugins.ls
                    },
                    'delete': {
                        'arguments': {
                            '-p,--plugin-id': plugin_id_argument(
                                hlp='The plugin id')
                        },
                        'help': 'Command for deleting a plugin',
                        'handler': cfy.plugins.delete
                    }
                }
            },
            'blueprints': {
                'help': "Manages Cloudify's Blueprints",
                'sub_commands': {
                    'upload': {
                        'arguments': {
                            '-p,--blueprint-path': {
                                'metavar': 'BLUEPRINT_FILE',
                                'dest': 'blueprint_path',
                                'type': argparse.FileType(),
                                'required': True,
                                'help': "Path to the application's blueprint file",
                                'completer': completion_utils.yaml_files_completer
                            },
                            '-b,--blueprint-id': argument_utils.remove_completer(blueprint_id_argument())
                        },
                        'help': 'command for uploading a blueprint to the management server',
                        'handler': cfy.blueprints.upload
                    },
                    'publish-archive': {
                        'arguments': {
                            '-l,--archive-location': {
                                'metavar': 'ARCHIVE_LOCATION',
                                'dest': 'archive_location',
                                'type': str,
                                'required': True,
                                'help': "Path or URL to the application's "
                                        "blueprint archive file",
                                'completer': completion_utils.archive_files_completer
                            },
                            '-n,--blueprint-filename': {
                                'metavar': 'BLUEPRINT_FILENAME',
                                'dest': 'blueprint_filename',
                                'type': str,
                                'required': False,
                                'help': "Name of the archive's main blueprint "
                                        "file",
                            },
                            '-b,--blueprint-id': argument_utils.remove_completer(blueprint_id_argument())
                        },
                        'help': 'command for publishing a blueprint '
                                'archive from a path or URL to the '
                                'management server',
                        'handler': cfy.blueprints.publish_archive
                    },
                    'download': {
                        'arguments': {
                            '-b,--blueprint-id': blueprint_id_argument(),
                            '-o,--output': {
                                'metavar': 'OUTPUT',
                                'type': str,
                                'help': 'The output file path of the blueprint to be downloaded',
                                'dest': 'output',
                                'required': False
                            }
                        },
                        'help': 'command for downloading a blueprint from the management server',
                        'handler': cfy.blueprints.download
                    },
                    'list': {
                        'help': 'command for listing all blueprints on the '
                                'Manager',
                        'handler': cfy.blueprints.ls
                    },
                    'delete': {
                        'arguments': {
                            '-b,--blueprint-id': blueprint_id_argument()
                        },
                        'help': 'command for deleting a blueprint',
                        'handler': cfy.blueprints.delete
                    },
                    'validate': {
                        'arguments': {
                            '-p,--blueprint-path': {
                                'metavar': 'BLUEPRINT_FILE',
                                'type': argparse.FileType(),
                                'dest': 'blueprint_path',
                                'required': True,
                                'help': "Path to the application's blueprint file",
                                'completer': completion_utils.yaml_files_completer
                            }
                        },
                        'help': 'command for validating a blueprint',
                        'handler': cfy.blueprints.validate
                    },
                    'get': {
                        'arguments': {
                            '-b,--blueprint-id': blueprint_id_argument()
                        },
                        'help': 'command for getting a blueprint by its id',
                        'handler': cfy.blueprints.get
                    },
                    'inputs': {
                        'arguments': {
                            '-b,--blueprint-id': blueprint_id_argument()
                        },
                        'help': 'command for listing all available blueprint inputs',
                        'handler': cfy.blueprints.inputs
                    }
                }
            },
            'snapshots': {
                'help': "Manages Cloudify's Snapshots",
                'sub_commands': {
                    'create': {
                        'arguments': {
                            '-s,--snapshot-id': argument_utils.remove_completer(
                                snapshot_id_argument(
                                    hlp='A unique id that will be assigned to the created snapshot'
                                )
                            ),
                            '--include-metrics': {
                                'dest': 'include_metrics',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Include metrics data'
                                        'in the snapshot'
                            },
                            '--exclude-credentials': {
                                'dest': 'exclude_credentials',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Do not store credentials in snapshot'
                            }
                        },
                        'help': 'Create a new snapshot',
                        'handler': cfy.snapshots.create
                    },
                    'upload': {
                        'arguments': {
                            '-p,--snapshot-path': {
                                'metavar': 'SNAPSHOT_FILE',
                                'dest': 'snapshot_path',
                                'type': argparse.FileType(),
                                'required': True,
                                'help': "Path to the manager's snapshot file",
                                'completer': completion_utils.yaml_files_completer
                            },
                            '-s,--snapshot-id': argument_utils.remove_completer(snapshot_id_argument('The id of the snapshot'))
                        },
                        'help': 'Upload a snapshot to the management server',
                        'handler': cfy.snapshots.upload
                    },
                    'download': {
                        'arguments': {
                            '-s,--snapshot-id': snapshot_id_argument('The id of the snapshot'),
                            '-o,--output': {
                                'metavar': 'OUTPUT',
                                'type': str,
                                'help': 'The output file path of the snapshot to be downloaded',
                                'dest': 'output',
                                'required': False
                            }
                        },
                        'help': 'Download a snapshot from the management server',
                        'handler': cfy.snapshots.download
                    },
                    'list': {
                        'help': 'List all snapshots on the manager',
                        'handler': cfy.snapshots.ls
                    },
                    'delete': {
                        'arguments': {
                            '-s,--snapshot-id': snapshot_id_argument('The id of the snapshot')
                        },
                        'help': 'Delete a snapshot from the manager',
                        'handler': cfy.snapshots.delete
                    },
                    'restore': {
                        'arguments': {
                            '-s,--snapshot-id': snapshot_id_argument('The id of the snapshot'),
                            '--without-deployments-envs': {
                                'dest': 'without_deployments_envs',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Restore snapshot without deployment environments'
                            },
                            '-f,--force': {
                                'dest': 'force',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Force restoring the snapshot on a dirty manager'
                            }
                        },
                        'help': 'Restore manager state to a specific snapshot',
                        'handler': cfy.snapshots.restore
                    }
                }
            },
            'agents': {
                'help': "Manages Cloudify's Agents",
                'sub_commands': {
                    'install': {
                        'arguments': {
                            '-d,--deployment-id': deployment_id_argument(
                                hlp='The id of the deployment to install agents for. If ommited, this '
                                'will install agents for all deployments'
                            ),
                            '-l,--include-logs': {
                                'dest': 'include_logs',
                                'action': 'store_true',
                                'help': 'Include logs in returned events'
                            }
                        },
                        'help':'command for installing agents on deployments',
                        'handler': cfy.agents.install
                    }
                }
            },
            'deployments': {
                'help': "Manages and Executes Cloudify's Deployments",
                'sub_commands': {
                    'create': {
                        'arguments': {
                            '-d,--deployment-id': argument_utils.remove_completer(
                                deployment_id_argument(
                                    hlp='A unique id that will be assigned to the created deployment'
                                )
                            ),
                            '-b,--blueprint-id': blueprint_id_argument(),
                            '-i,--inputs': {
                                'metavar': 'INPUTS',
                                'dest': 'inputs',
                                'required': False,
                                'help': 'Inputs file/string for the deployment creation ({0})'
                                        .format(FORMAT_INPUT_AS_YAML_OR_DICT)
                            }
                        },
                        'help': 'command for creating a deployment of a blueprint',
                        'handler': cfy.deployments.create
                    },
                    'delete': {
                        'arguments': {
                            '-d,--deployment-id': deployment_id_argument(
                                    hlp='the id of the deployment to delete'),
                            '-f,--ignore-live-nodes': {
                                'dest': 'ignore_live_nodes',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Delete the deployment even '
                                        'if there are existing live nodes for it'
                            }
                        },
                        'help': 'command for deleting a deployment',
                        'handler': cfy.deployments.delete
                    },
                    'list': {
                        'arguments': {
                            '-b,--blueprint-id': argument_utils.make_optional(
                                blueprint_id_argument()
                            )
                        },
                        'help': 'command for listing all deployments or all deployments'
                                ' of a blueprint',
                        'handler': cfy.deployments.ls
                    },
                    'outputs': {
                        'arguments': {
                            '-d,--deployment-id': deployment_id_argument(
                                hlp='The id of the deployment to get outputs for'
                            )
                        },
                        'help': 'command for getting a specific deployment outputs',
                        'handler': cfy.deployments.outputs
                    }
                }
            },
            'events': {
                'help': "Manages Cloudify's events",
                'sub_commands': {
                    'list': {
                        'arguments': {
                            '-l,--include-logs': {
                                'dest': 'include_logs',
                                'action': 'store_true',
                                'help': 'Includes logs in the returned events'
                            },
                            '-e,--execution-id': execution_id_argument(
                                hlp='The id of the execution to list events for'
                            ),
                            '--tail': {
                                'dest': 'tail',
                                'action': 'store_true',
                                'default': False,
                                'help': 'tail the events of the specified execution until it ends'
                            }
                        },
                        'help': 'Displays Events for different executions',
                        'handler': cfy.events.ls
                    }
                }
            },
            'executions': {
                'help': "Manages Cloudify's Executions",
                'sub_commands': {
                    'get': {
                        'arguments': {
                            '-e,--execution-id': execution_id_argument(
                                hlp='The id of the execution to get'
                            )
                        },
                        'help': 'command for getting an execution by its id',
                        'handler': cfy.executions.get
                    },
                    'list': {
                        'arguments': {
                            '-d,--deployment-id': deployment_id_argument(
                                hlp="filter executions for a given deployment by the deployment's id"
                            ),
                            '--system-workflows': {
                                'dest': 'include_system_workflows',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Include executions of system workflows.'
                            },
                        },
                        'help': 'command for listing all executions of a deployment',
                        'handler': cfy.executions.ls
                    },
                    'start': {
                        'arguments': {
                            '-w,--workflow': workflow_id_argument(
                                hlp='The workflow to start'),
                            '-p,--parameters': {
                                'metavar': 'PARAMETERS',
                                'dest': 'parameters',
                                'default': {},
                                'type': str,
                                'required': False,
                                'help': 'Parameters for the workflow execution ({0})'
                                        .format(FORMAT_INPUT_AS_YAML_OR_DICT)
                            },
                            '--allow-custom-parameters': {
                                'dest': 'allow_custom_parameters',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Allow the passing of custom parameters ('
                                        "parameters which were not defined in the workflow's schema in "
                                        'the blueprint) to the execution'
                            },
                            '--timeout': {
                                'dest': 'timeout',
                                'metavar': 'TIMEOUT',
                                'type': int,
                                'required': False,
                                'default': 900,
                                'help': 'Operation timeout in seconds (The execution itself will keep '
                                        'going, it is the CLI that will stop waiting for it to terminate)'
                            },
                            '-f,--force': {
                                'dest': 'force',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Whether the workflow should execute even if there is an ongoing'
                                        ' execution for the provided deployment'
                            },
                            '-l,--include-logs': {
                                'dest': 'include_logs',
                                'action': 'store_true',
                                'help': 'Include logs in returned events'
                            },
                            '-d,--deployment-id': deployment_id_argument(
                                hlp='The deployment id')
                        },
                        'help': 'Command for starting a workflow execution on a deployment',
                        'handler': cfy.executions.start
                    },
                    'cancel': {
                        'arguments': {
                            '-e,--execution-id': execution_id_argument(
                                hlp='The id of the execution to cancel'
                            ),
                            '-f,--force': {
                                'dest': 'force',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Terminate the execution abruptly, '
                                        'rather than request an orderly termination'
                            }
                        },
                        'help': 'Cancel an execution by its id',
                        'handler': cfy.executions.cancel
                    }
                }
            },
            'nodes': {
                'help': 'Manage nodes',
                'sub_commands': {
                    'get': {
                        'arguments': {
                            '--node-id': {
                                'dest': 'node_id',
                                'required': True,
                                'help': 'The ID of the node to get'
                            },
                            '-d,--deployment-id': {
                                'dest': 'deployment_id',
                                'required': True,
                                'help': 'Filter nodes for a given deployment according to the deployment ID'
                            }
                        },
                        'help': 'command for getting a node by its ID',
                        'handler': cfy.nodes.get
                    },
                    'list': {
                        'arguments': {
                            '-d,--deployment-id': {
                                'dest': 'deployment_id',
                                'required': False,
                                'help': 'Filter nodes for a given deployment according to the deployment ID'
                            }
                        },
                        'help': 'Command for getting all nodes',
                        'handler': cfy.nodes.ls
                    }
                }
            },
            'node-instances': {
                'help': 'Manage node instances',
                'sub_commands': {
                    'get': {
                        'arguments': {
                            '--node-instance-id': {
                                'dest': 'node_instance_id',
                                'required': True,
                                'help': 'The ID of the node instance to get'
                            }
                        },
                        'help': 'Command for getting a node instance according to it\'s ID',
                        'handler': cfy.node_instances.get
                    },
                    'list': {
                        'arguments': {
                            '-d,--deployment-id': {
                                'dest': 'deployment_id',
                                'required': False,
                                'help': 'Filter node instances for a given deployment according to the deployment ID'
                            },
                            '--node-name': {
                                'dest': 'node_name',
                                'required': False,
                                'help': 'Filter node instances according to the node name'
                            }
                        },
                        'help': 'Command for getting node instances',
                        'handler': cfy.node_instances.ls
                    }
                }
            },
            'workflows': {
                'help': 'Manages Deployment Workflows',
                'sub_commands': {
                    'get': {
                        'arguments': {
                            '-d,--deployment-id': deployment_id_argument(
                                hlp='The id of the deployment for which the workflow belongs'
                            ),
                            '-w,--workflow': workflow_id_argument(
                                hlp='The id of the workflow to get'
                            )
                        },
                        'help': 'command for getting a workflow by its name and deployment',
                        'handler': cfy.workflows.get
                    },
                    'list': {
                        'arguments': {
                            '-d,--deployment-id': deployment_id_argument(
                                hlp='The id of the deployment whose workflows to list'
                            )
                        },
                        'help': 'command for listing workflows for a deployment',
                        'handler': cfy.workflows.ls
                    }
                }
            },
            'local': {
                'help': 'Execute workflows locally',
                'sub_commands': {
                    'init': {
                        'help': 'Init a local workflow execution environment in '
                                'in the current working directory',
                        'arguments': {
                            '-p,--blueprint-path': {
                                'dest': 'blueprint_path',
                                'metavar': 'BLUEPRINT_PATH',
                                'type': str,
                                'required': True,
                                'help': 'Path to a blueprint'
                            },
                            '-i,--inputs': {
                                'metavar': 'INPUTS',
                                'dest': 'inputs',
                                'required': False,
                                'help': 'Inputs file/string for the local workflow creation ({0})'
                                        .format(FORMAT_INPUT_AS_YAML_OR_DICT)
                            },
                            '--install-plugins': {
                                'dest': 'install_plugins_',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Install necessary plugins of the given blueprint.'
                            }
                        },
                        'handler': cfy.local.init
                    },
                    'install-plugins': {
                        'help': 'Installs the necessary plugins for a given blueprint',
                        'arguments': {
                            '-p,--blueprint-path': {
                                'dest': 'blueprint_path',
                                'metavar': 'BLUEPRINT_PATH',
                                'type': str,
                                'required': True,
                                'help': 'Path to a blueprint'
                            }
                        },
                        'handler': cfy.local.install_plugins
                    },
                    'create-requirements': {
                        'help': 'Creates a PIP compliant requirements file for the given blueprint',
                        'arguments': {
                            '-p,--blueprint-path': {
                                'dest': 'blueprint_path',
                                'metavar': 'BLUEPRINT_PATH',
                                'type': str,
                                'required': True,
                                'help': 'Path to a blueprint'
                            },
                            '-o,--output': {
                                'metavar': 'REQUIREMENTS_OUTPUT',
                                'dest': 'output',
                                'required': False,
                                'help': 'Path to a file that will hold the '
                                        'requirements of the blueprint'
                            }
                        },
                        'handler': cfy.local.create_requirements
                    },
                    'execute': {
                        'help': 'Execute a workflow locally',
                        'arguments': {
                            '-w,--workflow':
                                argument_utils.remove_completer(
                                    workflow_id_argument(
                                        hlp='The workflow to execute locally'))
                            ,
                            '-p,--parameters': {
                                'metavar': 'PARAMETERS',
                                'dest': 'parameters',
                                'default': {},
                                'type': str,
                                'required': False,
                                'help': 'Parameters for the workflow execution ({0})'
                                        .format(FORMAT_INPUT_AS_YAML_OR_DICT)
                            },
                            '--allow-custom-parameters': {
                                'dest': 'allow_custom_parameters',
                                'action': 'store_true',
                                'default': False,
                                'help': 'Allow the passing of custom parameters ('
                                        "parameters which were not defined in the workflow's schema in "
                                        'the blueprint) to the execution'
                            },
                            '--task-retries': {
                                'metavar': 'TASK_RETRIES',
                                'dest': 'task_retries',
                                'default': 0,
                                'type': int,
                                'help': 'How many times should a task be retried in case '
                                        'it fails'
                            },
                            '--task-retry-interval': {
                                'metavar': 'TASK_RETRY_INTERVAL',
                                'dest': 'task_retry_interval',
                                'default': 1,
                                'type': int,
                                'help': 'How many seconds to wait before each task is retried'
                            },
                            '--task-thread-pool-size': {
                                'metavar': 'TASK_THREAD_POOL_SIZE',
                                'dest': 'task_thread_pool_size',
                                'default': 1,
                                'type': int,
                                'help': 'The size of the thread pool size to execute tasks in'
                            }
                        },
                        'handler': cfy.local.execute
                    },
                    'outputs': {
                        'help': 'Display outputs',
                        'arguments': {},
                        'handler': cfy.local.outputs
                    },
                    'instances': {
                        'help': 'Display node instances',
                        'arguments': {
                            '--node-id': {
                                'metavar': 'NODE_ID',
                                'dest': 'node_id',
                                'default': None,
                                'type': str,
                                'required': False,
                                'help': 'Only display node instances of this node id'
                            }
                        },
                        'handler': cfy.local.instances
                    }
                }
            },
            'status': {
                'help': "Show a management server's status",
                'handler': cfy.status
            },
            'dev': {
                'help': 'Executes fabric tasks on the management machine',
                'arguments': {
                    '-t,--task': {
                        'metavar': 'TASK',
                        'type': str,
                        'dest': 'task',
                        'help': 'name of fabric task to run',
                        'completer': completion_utils.dev_task_name_completer
                    },
                    '-a,--args': {
                        'nargs': argparse.REMAINDER,
                        'metavar': 'ARGS',
                        'dest': 'args',
                        'type': str,
                        'help': 'arguments for the fabric task'
                    },
                    '-p,--tasks-file': {
                        'dest': 'tasks_file',
                        'metavar': 'TASKS_FILE',
                        'type': str,
                        'help': 'Path to a tasks file',
                    }
                },
                'handler': cfy.dev
            },
            'ssh': {
                'help': 'SSH to management server',
                'arguments': {
                    '-c,--command': {
                        'dest': 'ssh_command',
                        'metavar': 'COMMAND',
                        'default': None,
                        'type': str,
                        'help': 'Execute command over SSH'
                    },
                    '-p,--plain': {
                        'dest': 'ssh_plain_mode',
                        'action': 'store_true',
                        'help': 'Leave authentication to user'
                    }
                },
                'handler': cfy.ssh
            },
            'bootstrap': {
                'help': 'Bootstrap a Cloudify management environment',
                'arguments': {
                    '-p,--blueprint-path': {
                        'dest': 'blueprint_path',
                        'metavar': 'BLUEPRINT_PATH',
                        'required': True,
                        'type': str,
                        'help': 'Path to a manager blueprint'
                    },
                    '-i,--inputs': {
                        'metavar': 'INPUTS',
                        'dest': 'inputs',
                        'required': False,
                        'help': 'Inputs file/string for a manager blueprint ({0})'
                                .format(FORMAT_INPUT_AS_YAML_OR_DICT)
                    },
                    '--keep-up-on-failure': {
                        'dest': 'keep_up',
                        'action': 'store_true',
                        'help': 'If the bootstrap fails,'
                                ' the management server will remain running'
                    },
                    '--skip-validations': {
                        'dest': 'skip_validations',
                        'action': 'store_true',
                        'help': 'Run bootstrap without,'
                                ' validating resources prior to bootstrapping the manager'
                    },
                    '--validate-only': {
                        'dest': 'validate_only',
                        'action': 'store_true',
                        'help': 'Run validations without'
                                ' actually performing the bootstrap process.'
                    },
                    '--install-plugins': {
                        'dest': 'install_plugins',
                        'action': 'store_true',
                        'default': False,
                        'help': 'Install necessary plugins of the given blueprint.'
                    },
                    '--task-retries': {
                        'metavar': 'TASK_RETRIES',
                        'dest': 'task_retries',
                        'default': 5,
                        'type': int,
                        'help': 'How many times should a task be retried in case '
                                'it fails'
                    },
                    '--task-retry-interval': {
                        'metavar': 'TASK_RETRY_INTERVAL',
                        'dest': 'task_retry_interval',
                        'default': 30,
                        'type': int,
                        'help': 'How many seconds to wait before each task is retried'
                    },
                    '--task-thread-pool-size': {
                        'metavar': 'TASK_THREAD_POOL_SIZE',
                        'dest': 'task_thread_pool_size',
                        'default': 1,
                        'type': int,
                        'help': 'The size of the thread pool size to execute tasks in'
                    }
                },
                'handler': cfy.bootstrap
            },
            'teardown': {
                'help': 'Teardown Cloudify',
                'arguments': {
                    '--ignore-deployments': {
                        'dest': 'ignore_deployments',
                        'action': 'store_true',
                        'help': 'Perform teardown even if deployments'
                                'exist on the manager'
                    },
                    '-f,--force': {
                        'dest': 'force',
                        'action': 'store_true',
                        'default': False,
                        'help': 'Confirmation for the teardown request'
                    }
                },
                'handler': cfy.teardown
            },
            'recover': {
                'help': 'Performs recovery of the management machine '
                        'and all its contained nodes.',
                'arguments': {
                    '-f,--force': {
                        'dest': 'force',
                        'action': 'store_true',
                        'default': False,
                        'help': 'Confirmation for the recovery request'
                    },
                    '--task-retries': {
                        'metavar': 'TASK_RETRIES',
                        'dest': 'task_retries',
                        'default': 5,
                        'type': int,
                        'help': 'How many times should a task be retried '
                                'in case it fails.'
                    },
                    '--task-retry-interval': {
                        'metavar': 'TASK_RETRY_INTERVAL',
                        'dest': 'task_retry_interval',
                        'default': 30,
                        'type': int,
                        'help': 'How many seconds to wait before each task is retried.'
                    },
                    '--task-thread-pool-size': {
                        'metavar': 'TASK_THREAD_POOL_SIZE',
                        'dest': 'task_thread_pool_size',
                        'default': 1,
                        'type': int,
                        'help': 'The size of the thread pool size to execute tasks in'
                    },
                    '-s,--snapshot-path': {
                        'metavar': 'SNAPSHOT_PATH',
                        'dest': 'snapshot_path',
                        'default': None,
                        'type': argparse.FileType(),
                        'help': 'Path to the snapshot that will be restored'
                    }
                },
                'handler': cfy.recover
            },
            'use': {
                'help': 'Use/switch to the specified management server',
                'arguments': {
                    '-t,--management-ip': {
                        'metavar': 'MANAGEMENT_IP',
                        'type': str,
                        'help': 'The cloudify management server ip address',
                        'dest': 'management_ip',
                        'required': True
                    },
                    '--port': {
                        'help': 'Specify the rest server port',
                        'default': DEFAULT_REST_PORT,
                        'type': int,
                        'dest': 'rest_port'
                    }
                },
                'handler': cfy.use
            },
            'init': {
                'help': 'Initialize cfy work environment',
                'arguments': {
                    '-r,--reset-config': {
                        'dest': 'reset_config',
                        'action': 'store_true',
                        'help': 'Overwriting existing configuration is allowed'
                    },
                },
                'handler': cfy.init
            }
        }
    }
