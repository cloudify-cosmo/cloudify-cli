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
import json

from cloudify_cli import commands as cfy
from cloudify_cli.config import completion_utils
from cloudify_cli.config import argument_utils


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


def deployment_id_argument(hlp):
    return {
        'dest': 'deployment_id',
        'metavar': 'DEPLOYMENT_ID',
        'type': str,
        'required': True,
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
                        'help': 'command for listing all uploaded blueprints',
                        'handler': cfy.blueprints.ls
                    },
                    'delete': {
                        'arguments': {
                            '-b,--blueprint-id': blueprint_id_argument()
                        },
                        'help': 'command for deleting an uploaded blueprint',
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
                                'help': 'Inputs file/string for the deployment creation (in JSON format)'
                            }
                        },
                        'help': 'command for creating a deployment of a blueprint',
                        'handler': cfy.deployments.create
                    },
                    'delete': {
                        'arguments': {
                            '-d,--deployment-id': argument_utils.remove_completer(
                                deployment_id_argument(
                                    hlp='the id of the deployment to delete'
                                )
                            ),
                            '-f,--ignore-live-nodes': {
                                'dest': 'ignore_live_nodes',
                                'action': 'store_true',
                                'default': False,
                                'help': 'A flag indicating whether or not to delete the deployment even '
                                        'if there exist live nodes for it'
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
                                'help': 'A flag whether to include logs in returned events'
                            },
                            '-e,--execution-id': execution_id_argument(
                                hlp='The id of the execution to list events for'
                            )
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
                            )
                        },
                        'help': 'command for listing all executions of a deployment',
                        'handler': cfy.executions.ls
                    },
                    'start': {
                        'arguments': {
                            '-w,--workflow': {
                                'metavar': 'WORKFLOW',
                                'dest': 'workflow',
                                'type': str,
                                'required': True,
                                'help': 'The workflow to execute'
                            },
                            '-p,--parameters': {
                                'metavar': 'PARAMETERS',
                                'dest': 'parameters',
                                'default': {},
                                'type': json.loads,
                                'required': False,
                                'help': 'Parameters for the workflow execution (in JSON format)'
                            },
                            '--allow-custom-parameters': {
                                'dest': 'allow_custom_parameters',
                                'action': 'store_true',
                                'default': False,
                                'help': 'A flag for allowing the passing of custom parameters ('
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
                                'help': 'A flag whether to include logs in returned events'
                            },
                            '-d,--deployment-id': {
                                'dest': 'deployment_id',
                                'metavar': 'DEPLOYMENT_ID',
                                'type': str,
                                'required': True,
                                'help': 'The deployment id'
                            }
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
                                'help': 'A flag indicating authorization to terminate the execution abruptly '
                                        'rather than request an orderly termination'
                            }
                        },
                        'help': 'Cancel an execution by its id',
                        'handler': cfy.executions.cancel
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
                        'help': 'name of fabric task to run'
                    },
                    '-a,--args': {
                        'nargs': argparse.REMAINDER,
                        'metavar': 'ARGS',
                        'dest': 'args',
                        'type': bytearray,
                        'help': 'arguments for the fabric task'
                    },
                    '--tasks-file': {
                        'dest': 'tasks_file',
                        'metavar': 'TASKS_FILE',
                        'type': str,
                        'help': 'Path to a tasks file'
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
                'help': 'Bootstrap Cloudify on the currently active provider',
                'arguments': {
                    '-c,--config-file': {
                        'dest': 'config_file_path',
                        'metavar': 'CONFIG_FILE',
                        'default': None,
                        'type': str,
                        'help': 'Path to a provider configuration file'
                    },
                    '--keep-up-on-failure': {
                        'dest': 'keep_up',
                        'action': 'store_true',
                        'help': 'A flag indicating that even if bootstrap fails,'
                                ' the instance will remain running'
                    },
                    '--skip-validations': {
                        'dest': 'skip_validations',
                        'action': 'store_true',
                        'help': 'A flag indicating that bootstrap will be run without,'
                                ' validating resources prior to bootstrapping the manager'
                    },
                    '--validate-only': {
                        'dest': 'validate_only',
                        'action': 'store_true',
                        'help': 'A flag indicating that validations will run without,'
                                ' actually performing the bootstrap process.'
                    }
                },
                'handler': cfy.bootstrap
            },
            'teardown': {
                'help': 'Teardown Cloudify',
                'arguments': {
                    '-c,--config-file': {
                        'dest': 'config_file_path',
                        'metavar': 'CONFIG_FILE',
                        'default': None,
                        'type': str,
                        'help': 'Path to a provider configuration file'
                    },
                    '--ignore-deployments': {
                        'dest': 'ignore_deployments',
                        'action': 'store_true',
                        'help': 'A flag indicating confirmation for teardown even if there '
                                'exist active deployments'
                    },
                    '--ignore-validation': {
                        'dest': 'ignore_validation',
                        'action': 'store_true',
                        'help': 'A flag indicating confirmation for teardown even if there '
                                'are validation conflicts'
                    },
                    '-f,--force': {
                        'dest': 'force',
                        'action': 'store_true',
                        'default': False,
                        'help': 'A flag indicating confirmation for the teardown request'
                    }
                },
                'handler': cfy.teardown
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
                    }
                },
                'handler': cfy.use
            },
            'init': {
                'help': 'Initialize configuration files for a specific cloud provider',
                'arguments': {
                    '-p,--provider': {
                        'metavar': 'PROVIDER',
                        'type': str,
                        'dest': 'provider',
                        'help': 'Command for initializing configuration files for a'
                                ' specific provider'
                    },
                    '-r,--reset-config': {
                        'dest': 'reset_config',
                        'action': 'store_true',
                        'help': 'A flag indicating overwriting existing configuration is allowed'
                    },
                    '--creds': {
                        'dest': 'creds',
                        'metavar': 'PROVIDER_CREDENTIALS',
                        'type': str,
                        'help': 'a comma separated list of key=value credentials'
                    }
                },
                'handler': cfy.init
            }
        }
    }
