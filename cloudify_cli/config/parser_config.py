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

import os
import argparse

from cloudify_cli import commands as cfy
from cloudify_cli import utils
from cloudify_cli.config import completion_utils
from cloudify_cli.config.argument_utils import remove_type
from cloudify_cli.config.argument_utils import remove_completer
from cloudify_cli.config.argument_utils import make_required
from cloudify_cli.config.argument_utils import make_optional
from cloudify_cli.constants import DEFAULT_REST_PORT
from cloudify_cli.constants import DEFAULT_BLUEPRINT_FILE_NAME
from cloudify_cli.constants import DEFAULT_BLUEPRINT_PATH
from cloudify_cli.constants import DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND
from cloudify_cli.constants import DEFAULT_TIMEOUT
from cloudify_cli.constants import DEFAULT_PARAMETERS
from cloudify_cli.constants import DEFAULT_TASK_THREAD_POOL_SIZE
from cloudify_cli.constants import DEFAULT_INSTALL_WORKFLOW
from cloudify_cli.constants import DEFAULT_UNINSTALL_WORKFLOW

FORMAT_INPUT_AS_YAML_OR_DICT = 'formatted as YAML or as "key1=value1;key2=value2"'


def manager_blueprint_path_argument():

    # These are specific attributes to the manager blueprint path argument
    argument = {
        'metavar': 'BLUEPRINT_FILE',
        'type': argparse.FileType(),
        'completer': completion_utils.yaml_files_completer
    }
    hlp = "Path to the application's blueprint file. " \
          "(default: {0})".format(DEFAULT_BLUEPRINT_PATH)

    # Update the specific 'manager blueprint path argument' attributes with
    # those that are shared with the 'local blueprint path argument'
    argument.update(local_blueprint_path_argument(hlp))

    return argument


def local_blueprint_path_argument(hlp):
    return {
        'dest': 'blueprint_path',
        'required': True,
        'help': hlp
    }


def blueprint_id_argument():
    return {
        'help': "The blueprint's id",
        'dest': 'blueprint_id',
        'required': True,
        'completer':
            completion_utils.objects_args_completer_maker('blueprints')
    }


def validate_blueprint_argument():
    return {
        'dest': 'validate_blueprint',
        'action': 'store_true',
        'help': 'Validate the blueprint before uploading it '
                'to the manager'
    }


def archive_location_argument():
    return {
        'dest': 'archive_location',
        'required': True,
        'help': "Path or URL to the application's blueprint archive file",
        'completer': completion_utils.archive_files_completer
    }


def deployment_id_argument(hlp):
    return {
        'dest': 'deployment_id',
        'help': hlp,
        'completer': completion_utils.objects_args_completer_maker('deployments')
    }


def inputs_argument(hlp):
    return {
        'dest': 'inputs',
        'help': hlp,
        'action': 'append'
    }


def execution_id_argument(hlp):
    return {
        'dest': 'execution_id',
        'required': True,
        'help': hlp,
        'completer': completion_utils.objects_args_completer_maker('executions')
    }


def workflow_id_argument(hlp):
    return {
        'metavar': 'WORKFLOW',
        'dest': 'workflow_id',
        'required': True,
        'help': hlp,
        'completer': completion_utils.workflow_id_completer
    }


def parameters_argument():
    return {
        'dest': 'parameters',
        'action': 'append',
        'help': ('Parameters for the workflow execution ({0}). '
        'This argument can be used multiple times.')
        .format(FORMAT_INPUT_AS_YAML_OR_DICT)
    }


def allow_custom_parameters_argument():
    return {
        'dest': 'allow_custom_parameters',
        'action': 'store_true',
        'help': 'Allow the passing of custom parameters ('
                "parameters which were not defined in the workflow's schema "
                'in the blueprint) to the execution'
    }


def force_argument(hlp):
    return {
        'dest': 'force',
        'action': 'store_true',
        'help': hlp
    }


def timeout_argument():
    return {
        'dest': 'timeout',
        'type': int,
        'default': DEFAULT_TIMEOUT,
        'help': 'Operation timeout in seconds (The execution itself will keep '
                'going. It is the CLI that will stop waiting for it to '
                'terminate)'
    }


def include_logs_argument():
    return {
        'dest': 'include_logs',
        'action': 'store_true',
        'help': 'Include logs in returned events'
    }


def install_plugins_argument():
    return {
        'dest': 'install_plugins',
        'action': 'store_true',
        'help': 'Install necessary plugins of the given blueprint'
    }


def task_retries_argument(default_value):
    return {
        'dest': 'task_retries',
        'default': default_value,
        'type': int,
        'help': 'How many times should a task be retried in case it fails'
    }


def task_retry_interval_argument(default_value):
    return {
        'dest': 'task_retry_interval',
        'default': default_value,
        'type': int,
        'help': 'How many seconds to wait before each task is retried'
    }


def task_thread_pool_size_argument():
    return {
        'dest': 'task_thread_pool_size',
        'default': DEFAULT_TASK_THREAD_POOL_SIZE,
        'type': int,
        'help': 'The size of the thread pool to execute tasks in'
    }


def plugin_id_argument(hlp):
    return {
        'help': hlp,
        'dest': 'plugin_id',
        'required': True,
        'completer': completion_utils.objects_args_completer_maker('plugins')
    }


def snapshot_id_argument(hlp):
    return {
        'help': hlp,
        'dest': 'snapshot_id',
        'required': True,
        'completer': completion_utils.objects_args_completer_maker('snapshots')
    }


def auto_generate_ids_argument():
    return {
        'dest': 'auto_generate_ids',
        'action': 'store_true',
        'help': 'Auto generate blueprint and deployment ids'
    }


def parser_config():
    return {
        'description': 'Manages Cloudify in different Cloud Environments',
        'arguments': {
            '--version': {
                'help': 'Show version information and exit',
                'action': cfy.version
            }
        },
        'commands': {
            'logs': {
                'help': 'Handle Cloudify Manager logs',
                'sub_commands': {
                    'get': {
                        'arguments': {
                            '-d,--destination-path': {
                                'dest': 'destination_path',
                                'help': 'Destination path of the downloaded archive',
                                'default': utils.get_cwd(),
                            }
                        },
                        'help': "Retrieve an archive containing a Manager's logs (default: cwd)",
                        'handler': cfy.logs.get
                    },
                    'purge': {
                        'arguments': {
                            '-f,--force': {
                                'dest': 'force',
                                'help': 'Force purge. This flag is mandatory',
                                'required': True,
                                'action': 'store_true',
                            },
                            '--backup-first': {
                                'dest': 'backup_first',
                                'help': 'Whether to backup before purging.'
                                        'Backup will be in tar.gz format.',
                                'action': 'store_true',
                            }
                        },
                        'help': "Delete a Manager's logs",
                        'handler': cfy.logs.purge
                    },
                    'backup': {
                        'help': "Back up a Manager's logs",
                        'handler': cfy.logs.backup
                    }
                }
            },
            'install': {
                'help': 'Install an application on a Cloudify Manager',
                'arguments': {
                    '-p,--blueprint-path':
                        make_optional(
                                remove_type(
                                        manager_blueprint_path_argument())
                        ),
                    '-b,--blueprint-id': remove_completer(
                            make_optional(blueprint_id_argument(
                            ))
                        ),
                    '--validate': validate_blueprint_argument(),
                    '-l,--archive-location': make_optional(
                            archive_location_argument()),
                    '-n,--blueprint-filename': {
                        'dest': 'blueprint_filename',
                        'help': "The name of the archive's main "
                                "blueprint file. (default: {0})"
                                .format(DEFAULT_BLUEPRINT_FILE_NAME)
                        },
                    '-d,--deployment-id': deployment_id_argument(
                            hlp='The id of the deployed blueprint'
                        ),
                    '-i,--inputs':
                        inputs_argument('Inputs file/string for the deployment'
                                        ' creation ({0}). '
                                        'This argument can be used multiple times. '
                                        '(default: {1})'
                                        .format(FORMAT_INPUT_AS_YAML_OR_DICT,
                                                DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND)
                                        ),
                    '-w,--workflow': make_optional(workflow_id_argument(
                            hlp='The workflow to start '
                                '(default: {0})'
                                .format(DEFAULT_INSTALL_WORKFLOW)
                            )
                        ),
                    '--parameters': parameters_argument(),
                    '--allow-custom-parameters':
                        allow_custom_parameters_argument(),
                    '--timeout': timeout_argument(),
                    '--include-logs': include_logs_argument(),
                    '-g,--auto-generate-ids': auto_generate_ids_argument()
                },
                'handler': cfy.install
            },
            'uninstall': {
                'help': 'Uninstall an existing application '
                        'from the Cloudify Manager',
                'arguments': {
                    '-d,--deployment-id': make_required(
                            deployment_id_argument(
                                hlp='The id of the deployment you wish to '
                                    'uninstall'
                            )
                        ),
                    '-w,--workflow': make_optional(workflow_id_argument(
                            hlp='The workflow to start (default: {0}'
                                .format(DEFAULT_UNINSTALL_WORKFLOW))
                        ),
                    '--parameters': parameters_argument(),
                    '--allow-custom-parameters':
                        allow_custom_parameters_argument(),
                    '--timeout': timeout_argument(),
                    '-l,--include-logs': include_logs_argument()
                },
                'handler': cfy.uninstall
            },
            'plugins': {
                'help': "Manage Cloudify's plugins",
                'sub_commands': {
                    'upload': {
                        'arguments': {
                            '-p,--plugin-path': {
                                'metavar': 'PLUGIN_FILE',
                                'dest': 'plugin_path',
                                'type': argparse.FileType(),
                                'required': True,
                                'help': 'Path to a plugin Wagon (`.wgn` file)',
                                'completer': completion_utils.yaml_files_completer
                            }
                        },
                        'help': 'Upload a plugin to the management server',
                        'handler': cfy.plugins.upload
                    },
                    'get': {
                        'arguments': {
                            '-p,--plugin-id': plugin_id_argument(
                                hlp='Plugin id')
                        },
                        'help': 'List all modules according to their plugin id',
                        'handler': cfy.plugins.get
                    },
                    'download': {
                        'arguments': {
                            '-p,--plugin-id': plugin_id_argument(
                                hlp='Plugin id'),
                            '-o,--output': {
                                'help': 'Path for the downloaded plugin',
                                'dest': 'output',

                            }
                        },
                        'help': 'Download a plugin from the Manager',
                        'handler': cfy.plugins.download
                    },
                    'list': {
                        'help': 'List all the plugins on the Manager',
                        'handler': cfy.plugins.ls
                    },
                    'delete': {
                        'arguments': {
                            '-p,--plugin-id': plugin_id_argument(
                                hlp='The plugin id')
                        },
                        'help': 'Delete a plugin from the manager',
                        'handler': cfy.plugins.delete
                    }
                }
            },
            'blueprints': {
                'help': "Manage Cloudify's Blueprints",
                'sub_commands': {
                    'upload': {
                        'arguments': {
                            '-p,--blueprint-path':
                                manager_blueprint_path_argument(),
                            '-b,--blueprint-id': remove_completer(
                                    blueprint_id_argument()),
                            '--validate': validate_blueprint_argument()
                        },
                        'help': 'Upload a blueprint to the Manager',
                        'handler': cfy.blueprints.upload
                    },
                    'publish-archive': {
                        'arguments': {
                            '-l,--archive-location': archive_location_argument(),
                            '-n,--blueprint-filename': {
                                'dest': 'blueprint_filename',
                                'help': "The name of the archive's main "
                                        "blueprint file"
                            },
                            '-b,--blueprint-id': remove_completer(blueprint_id_argument())
                        },
                        'help': 'Publish a blueprint archive from a path or '
                                'a URL to the Manager',
                        'handler': cfy.blueprints.publish_archive
                    },
                    'download': {
                        'arguments': {
                            '-b,--blueprint-id': blueprint_id_argument(),
                            '-o,--output': {
                                'help': 'The output file path of the blueprint to be downloaded',
                                'dest': 'output',
                            }
                        },
                        'help': 'Download a blueprint from the Manager',
                        'handler': cfy.blueprints.download
                    },
                    'list': {
                        'help': 'List all blueprints on the Manager',
                        'handler': cfy.blueprints.ls
                    },
                    'delete': {
                        'arguments': {
                            '-b,--blueprint-id': blueprint_id_argument()
                        },
                        'help': 'Delete a blueprint from the manager',
                        'handler': cfy.blueprints.delete
                    },
                    'validate': {
                        'arguments': {
                            '-p,--blueprint-path':
                                manager_blueprint_path_argument(),
                        },
                        'help': 'Validate a blueprint',
                        'handler': cfy.blueprints.validate
                    },
                    'get': {
                        'arguments': {
                            '-b,--blueprint-id': blueprint_id_argument()
                        },
                        'help': 'Get a blueprint by its id',
                        'handler': cfy.blueprints.get
                    },
                    'inputs': {
                        'arguments': {
                            '-b,--blueprint-id': blueprint_id_argument()
                        },
                        'help': "List a blueprint's inputs",
                        'handler': cfy.blueprints.inputs
                    }
                }
            },
            'snapshots': {
                'help': "Manage Cloudify's Snapshots",
                'sub_commands': {
                    'create': {
                        'arguments': {
                            '-s,--snapshot-id': remove_completer(
                                snapshot_id_argument(
                                    hlp='A unique id that will be assigned to the created snapshot'
                                )
                            ),
                            '--include-metrics': {
                                'dest': 'include_metrics',
                                'action': 'store_true',
                                'help': 'Include metrics data'
                                        'in the snapshot'
                            },
                            '--exclude-credentials': {
                                'dest': 'exclude_credentials',
                                'action': 'store_true',
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
                            '-s,--snapshot-id': remove_completer(snapshot_id_argument('The id of the snapshot'))
                        },
                        'help': 'Upload a snapshot to the Manager',
                        'handler': cfy.snapshots.upload
                    },
                    'download': {
                        'arguments': {
                            '-s,--snapshot-id': snapshot_id_argument('The id of the snapshot'),
                            '-o,--output': {
                                'help': 'The output file path of the snapshot to be downloaded',
                                'dest': 'output',

                            }
                        },
                        'help': 'Download a snapshot from the Manager',
                        'handler': cfy.snapshots.download
                    },
                    'list': {
                        'help': 'List all snapshots on the Manager',
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
                                'help': 'Restore snapshot without deployment environments'
                            },
                            '-f,--force':
                                force_argument(
                                        hlp='Force restoring the snapshot on '
                                            'a Manager with existing '
                                            'blueprints and/or deployments')
                        },
                        'help': 'Restore manager state to a specific snapshot',
                        'handler': cfy.snapshots.restore
                    }
                }
            },
            'agents': {
                'help': "Manage Cloudify's Agents",
                'sub_commands': {
                    'install': {
                        'arguments': {
                            '-d,--deployment-id': deployment_id_argument(
                                hlp='The id of the deployment to install '
                                    'agents for. If omitted, this will '
                                    'install agents for all deployments'
                            ),
                            '-l,--include-logs': include_logs_argument()
                        },
                        'help':'Install agents on deployments',
                        'handler': cfy.agents.install
                    }
                }
            },
            'deployments': {
                'help': "Manage Cloudify's Deployments",
                'sub_commands': {
                    'create': {
                        'arguments': {
                            '-d,--deployment-id': make_required(
                                remove_completer(
                                    deployment_id_argument(
                                        hlp='A unique id that will be assigned'
                                            ' to the created deployment'
                                    )
                                )
                            ),
                            '-b,--blueprint-id': blueprint_id_argument(),
                            '-i,--inputs': inputs_argument(
                                hlp='Inputs file/string for the deployment creation ({0}) '
                                    'This argument can be used multiple times.'
                                    .format(FORMAT_INPUT_AS_YAML_OR_DICT)
                            )
                        },
                        'help': 'Create a deployment from a blueprint',
                        'handler': cfy.deployments.create
                    },
                    'delete': {
                        'arguments': {
                            '-d,--deployment-id': make_required(
                                deployment_id_argument(
                                    hlp='The id of the deployment to delete')
                            ),
                            '-f,--ignore-live-nodes': {
                                'dest': 'ignore_live_nodes',
                                'action': 'store_true',
                                'help': 'Delete the deployment even if '
                                        'there are existing live nodes for it'
                            }
                        },
                        'help': 'Delete a deployment from the manager',
                        'handler': cfy.deployments.delete
                    },
                    'list': {
                        'arguments': {
                            '-b,--blueprint-id': make_optional(
                                blueprint_id_argument()
                            )
                        },
                        'help': 'List the all deployments on the manager, '
                                'or all deployments of a specific blueprint',
                        'handler': cfy.deployments.ls
                    },
                    'outputs': {
                        'arguments': {
                            '-d,--deployment-id': make_required(
                                deployment_id_argument(
                                    hlp='The id of the deployment to get '
                                        'outputs for'
                                )
                            )
                        },
                        'help': 'Get outputs for a specific deployment',
                        'handler': cfy.deployments.outputs
                    }
                }
            },
            'events': {
                'help': "Manage Cloudify's events",
                'sub_commands': {
                    'list': {
                        'arguments': {
                            '-l,--include-logs': include_logs_argument(),
                            '-e,--execution-id': execution_id_argument(
                                hlp='The id of the execution to list events for'
                            ),
                            '--tail': {
                                'dest': 'tail',
                                'action': 'store_true',
                                'help': 'Tail the events of the specified execution until it ends'
                            }
                        },
                        'help': 'Display Events for different executions',
                        'handler': cfy.events.ls
                    }
                }
            },
            'executions': {
                'help': "Manage Cloudify's Executions",
                'sub_commands': {
                    'get': {
                        'arguments': {
                            '-e,--execution-id': execution_id_argument(
                                hlp='The id of the execution to get'
                            )
                        },
                        'help': 'Get an execution by its id',
                        'handler': cfy.executions.get
                    },
                    'list': {
                        'arguments': {
                            '-d,--deployment-id': deployment_id_argument(
                                hlp='The Deployment id to list executions for'
                            ),
                            '--system-workflows': {
                                'dest': 'include_system_workflows',
                                'action': 'store_true',
                                'help': 'Include executions of '
                                        'system workflows'
                            },
                        },
                        'help': 'List all running executions, or all '
                                'executions for a specific deployment',
                        'handler': cfy.executions.ls
                    },
                    'start': {
                        'arguments': {
                            '-w,--workflow': workflow_id_argument(
                                hlp='The workflow to start'),
                            '-p,--parameters': parameters_argument(),
                            '--allow-custom-parameters':
                                allow_custom_parameters_argument(),
                            '--timeout': timeout_argument(),
                            '-f,--force':
                                force_argument(
                                    hlp='Execute the workflow even if there '
                                        'is an ongoing execution for the '
                                        'given deployment'
                                ),
                            '-l,--include-logs': include_logs_argument(),
                            '-d,--deployment-id': make_required(
                                deployment_id_argument(
                                    hlp='The deployment id')
                            )
                        },
                        'help': 'Start executing a workflow '
                                'on a given deployment',
                        'handler': cfy.executions.start
                    },
                    'cancel': {
                        'arguments': {
                            '-e,--execution-id': execution_id_argument(
                                hlp='The id of the execution to cancel'
                            ),
                            '-f,--force': force_argument(
                                    hlp='Terminate the execution abruptly, '
                                        'rather than request an orderly '
                                        'termination')
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
                                'help': "The node's id"
                            },
                            '-d,--deployment-id': make_required(
                                    deployment_id_argument(
                                            hlp='The deployment id to which '
                                                'the node is related'))
                        },
                        'help': 'Get information about a specific node',
                        'handler': cfy.nodes.get
                    },
                    'list': {
                        'arguments': {
                            '-d,--deployment-id': deployment_id_argument(
                                    hlp='The id of the deployment to list '
                                        'nodes for. If omitted, this will '
                                        'list nodes for all deployments')
                        },
                        'help': 'List nodes for all deployments, or for a '
                                'specific deployment',
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
                        'help': "Get a node instance according to its ID",
                        'handler': cfy.node_instances.get
                    },
                    'list': {
                        'arguments': {
                            '-d,--deployment-id': deployment_id_argument(
                                    hlp='The id of the deployment to list '
                                        'node instances for. If omitted, '
                                        'this will list node instances'
                                        'for all deployments)'),
                            '--node-name': {
                                'dest': 'node_name',
                                'help': "The node's name"
                            }
                        },
                        'help': 'List node instances for all deployments,'
                                'or for a specific deployment',
                        'handler': cfy.node_instances.ls
                    }
                }
            },
            'workflows': {
                'help': 'Manage Deployment Workflows',
                'sub_commands': {
                    'get': {
                        'arguments': {
                            '-d,--deployment-id': make_required(
                                deployment_id_argument(
                                    hlp='The id of the deployment to which '
                                        'the workflow belongs'
                                )
                            ),
                            '-w,--workflow': workflow_id_argument(
                                hlp='The id of the workflow to get'
                            )
                        },
                        'help': 'Get a workflow by its name and deployment',
                        'handler': cfy.workflows.get
                    },
                    'list': {
                        'arguments': {
                            '-d,--deployment-id': make_required(
                                deployment_id_argument(
                                    hlp='The id of the deployment whose '
                                        'workflows to list'
                                )
                            )
                        },
                        'help': 'List workflows for a deployment',
                        'handler': cfy.workflows.ls
                    }
                }
            },
            'local': {
                'help': 'Manage local workflows',
                'sub_commands': {
                    'install': {
                        'help': 'Install an application',
                        'arguments': {
                            '-p,--blueprint-path':
                                make_optional(
                                        local_blueprint_path_argument(
                                                hlp="Path to the application's"
                                                    "blueprint file. (default: "
                                                    "{0})".format(DEFAULT_BLUEPRINT_PATH)
                                        )
                                ),
                            '-i,--inputs':
                                inputs_argument('Inputs file/string for the '
                                                'deployment creation ({0}). '
                                                'This argument can be used multiple times. '
                                                '(default: {1})'
                                                .format(FORMAT_INPUT_AS_YAML_OR_DICT,
                                                        DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND)
                                                ),
                            '--install-plugins': install_plugins_argument(),
                            '-w,--workflow': make_optional(
                                    workflow_id_argument(
                                            hlp='The workflow to start '
                                                '(default: {0}'
                                                .format(DEFAULT_INSTALL_WORKFLOW)
                                    )
                                ),
                            '--parameters': parameters_argument(),
                            '--allow-custom-parameters':
                                allow_custom_parameters_argument(),
                            '--task-retries': task_retries_argument(0),
                            '--task-retry-interval':
                                task_retry_interval_argument(1),
                            '--task-thread-pool-size':
                                task_thread_pool_size_argument()
                        },
                        'handler': cfy.local.install
                    },
                    'uninstall': {
                        'help': 'Uninstall an application',
                        'arguments': {
                            '-w,--workflow': make_optional(
                                    workflow_id_argument(
                                            hlp='The workflow to start '
                                                '(default: {0}'
                                                .format(DEFAULT_UNINSTALL_WORKFLOW)
                                    )
                                ),
                            '--parameters': parameters_argument(),
                            '--allow-custom-parameters':
                                allow_custom_parameters_argument(),
                            '--task-retries': task_retries_argument(0),
                            '--task-retry-interval':
                                task_retry_interval_argument(1),
                            '--task-thread-pool-size':
                                task_thread_pool_size_argument()
                        },
                        'handler': cfy.local.uninstall
                    },
                    'init': {
                        'help': 'Init a local workflow execution environment '
                                'in the current working directory',
                        'arguments': {
                            '-p,--blueprint-path':
                                local_blueprint_path_argument(
                                        hlp='Path to a blueprint'
                                ),
                            '-i,--inputs': inputs_argument(
                                    hlp='Inputs files/strings for the local workflow creation ({0}). '
                                        'This argument can be used multiple times.'
                                        .format(FORMAT_INPUT_AS_YAML_OR_DICT)
                                ),
                            '--install-plugins': install_plugins_argument()
                        },
                        'handler': cfy.local.init
                    },
                    'install-plugins': {
                        'help': 'Install the necessary plugins for a given blueprint',
                        'arguments': {
                            '-p,--blueprint-path':
                                local_blueprint_path_argument(
                                        hlp='Path to a blueprint'
                                ),
                        },
                        'handler': cfy.local.install_plugins
                    },
                    'create-requirements': {
                        'help': 'Create a pip-compliant requirements file for a given blueprint',
                        'arguments': {
                            '-p,--blueprint-path':
                                local_blueprint_path_argument(
                                        hlp='Path to a blueprint'
                                ),
                            '-o,--output': {
                                'metavar': 'REQUIREMENTS_OUTPUT',
                                'dest': 'output',
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
                                remove_completer(
                                    workflow_id_argument(
                                        hlp='The workflow to execute locally'))
                            ,
                            '-p,--parameters': parameters_argument(),
                            '--allow-custom-parameters':
                                allow_custom_parameters_argument(),
                            '--task-retries': task_retries_argument(0),
                            '--task-retry-interval':
                                task_retry_interval_argument(1),
                            '--task-thread-pool-size':
                                task_thread_pool_size_argument()
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
                                'dest': 'node_id',
                                'help': 'Display only node instances of this node id'
                            }
                        },
                        'handler': cfy.local.instances
                    }
                }
            },
            'status': {
                'help': "Show the Manager's status",
                'handler': cfy.status
            },
            'dev': {
                'help': 'Execute fabric tasks on the management machine',
                'arguments': {
                    '-t,--task': {
                        'dest': 'task',
                        'help': 'Name of fabric task to run',
                        'completer': completion_utils.dev_task_name_completer
                    },
                    '-a,--args': {
                        'nargs': argparse.REMAINDER,
                        'dest': 'args',
                        'help': 'Arguments for the fabric task'
                    },
                    '-p,--tasks-file': {
                        'dest': 'tasks_file',
                        'help': 'Path to a tasks file',
                    }
                },
                'handler': cfy.dev
            },
            'ssh': {
                'help': 'SSH to the machine the Manager is located on',
                'arguments': {
                    '-c,--command': {
                        'dest': 'ssh_command',
                        'metavar': 'COMMAND',
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
                'help': 'Bootstrap a Cloudify Manager',
                'arguments': {
                    '-p,--blueprint-path':
                        local_blueprint_path_argument(
                                hlp='Path to a blueprint'
                        ),
                    '-i,--inputs': inputs_argument(
                        hlp='Inputs file/string for a manager blueprint ({0}) '
                            'This argument can be used multiple times.'
                            .format(FORMAT_INPUT_AS_YAML_OR_DICT)
                    ),
                    '--keep-up-on-failure': {
                        'dest': 'keep_up',
                        'action': 'store_true',
                        'help': 'If the bootstrap fails,'
                                ' the Manager will remain running'
                    },
                    '--skip-validations': {
                        'dest': 'skip_validations',
                        'action': 'store_true',
                        'help': 'Run bootstrap without '
                                'validating resources prior to bootstrapping the manager'
                    },
                    '--validate-only': {
                        'dest': 'validate_only',
                        'action': 'store_true',
                        'help': 'Run validations without '
                                'actually performing the bootstrap process'
                    },
                    '--install-plugins': install_plugins_argument(),
                    '--task-retries': task_retries_argument(5),
                    '--task-retry-interval': task_retry_interval_argument(30),
                    '--task-thread-pool-size':
                        task_thread_pool_size_argument()
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
                    '-f,--force': force_argument(
                            hlp='Confirmation for the teardown request')
                },
                'handler': cfy.teardown
            },
            'recover': {
                'help': 'Perform recovery of the management machine '
                        'and all its contained nodes',
                'arguments': {
                    '-f,--force': force_argument(
                            hlp='Confirmation for the recovery request'
                    ),
                    '--task-retries': task_retries_argument(5),
                    '--task-retry-interval': task_retry_interval_argument(30),
                    '--task-thread-pool-size':
                        task_thread_pool_size_argument(),
                    '-s,--snapshot-path': {
                        'dest': 'snapshot_path',
                        'type': argparse.FileType(),
                        'help': 'Path to the snapshot that will be restored'
                    }
                },
                'handler': cfy.recover
            },
            'use': {
                'help': 'Use/switch to a specific Cloudify Manager',
                'arguments': {
                    '-t,--management-ip': {
                        'help': "The Cloudify Manager ip's address",
                        'dest': 'management_ip',
                        'required': True
                    },
                    '--port': {
                        'help': "The rest server's port",
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
