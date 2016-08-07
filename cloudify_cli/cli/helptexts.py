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

VERBOSE = \
    "Show verbose output. You can supply this up to three times (i.e. -vvv)"
VERSION = (
    "Display the version and exit (if a manager is used, its version will "
    "also show)"
)

INPUTS_PARAMS_USAGE = (
    '(Can be provided as wildcard based paths '
    '(*.yaml, /my_inputs/, etc..) to YAML files, a JSON string or as '
    'key1=value1;key2=value2). This argument can be used multiple times'
)
WORKFLOW_TO_EXECUTE = "The workflow to execute [default: {0}]"

BLUEPRINT_PATH = "The path to the application's blueprint file"
BLUEPRINT_ID = "The unique identifier for the blueprint"
VALIDATE_BLUEPRINT = "Validate the blueprint first"

RESET_CONTEXT = "Reset the working environment"
HARD_RESET = "Hard reset the configuration, including coloring and loggers"
SHOW_ACTIVE_CONNECTION_INFORMATION = \
    "Show connection information for the active manager"
ENABLE_COLORS = "Enable colors in logger (use --hard when working with" \
                " an initialized environment) [default: False]"

OUTPUT_PATH = "The local path to download to"
BLUEPRINT_FILENAME = (
    "The name of the archive's main blueprint file. "
    "This is only relevant if uploading an archive")
INPUTS = "Inputs for the deployment {0}".format(INPUTS_PARAMS_USAGE)
PARAMETERS = "Parameters for the workflow {0}".format(INPUTS_PARAMS_USAGE)
ALLOW_CUSTOM_PARAMETERS = (
    "Allow passing custom parameters (which were not defined in the "
    "workflow's schema in the blueprint) to the execution"
)
INSTALL_PLUGINS = "Install the necessary plugins for the given blueprint"
TASK_RETRIES = \
    "How many times should a task be retried in case of failure [default: {0}]"
TASK_THREAD_POOL_SIZE = \
    "The size of the thread pool to execute tasks in [default: {0}]"

SSH_COMMAND = "Execute a command on the manager over SSH"
SSH_HOST_SESSION = "Host an SSH tmux session"
SSH_CONNECT_TO_SESSION = "Join an SSH tmux session"
SSH_LIST_SESSIONS = "List available SSH tmux sessions"

OPERATION_TIMEOUT = (
    "Operation timeout in seconds (The execution itself will keep going, but "
    "the CLI will stop waiting for it to terminate) [default: {0}]"
)
INCLUDE_LOGS = "Include logs in returned events [default: True]"
JSON_OUTPUT = "Output events in a consumable JSON format"

SKIP_INSTALL = "Skip install lifecycle operations"
SKIP_UNINSTALL = "Skip uninstall lifecycle operations"
FORCE_UPDATE = (
    "Force running update in case a previous update on this deployment has "
    "failed to finished successfully"
)

DEPLOYMENT_ID = "The unique identifier for the deployment"
IGNORE_LIVE_NODES = (
    "Delete the deployment even if there are existing live nodes for it"
)

INCLUDE_SYSTEM_WORKFLOWS = "Include executions of system workflows"

FORCE_CONCURRENT_EXECUTION = (
    "Execute the workflow even if there is an ongoing execution for the given "
    "deployment"
)
FORCE_CANCEL_EXECUTION = (
    "Terminate the execution abruptly, rather than request an orderly "
    "termination"
)

INIT_LOCAL = "Initialize environment for local executions"
NODE_NAME = "The node's name"

FORCE_PURGE_LOGS = "Force purge. This flag is mandatory"
BACKUP_LOGS_FIRST = "Whether to backup before purging"

RESTORE_SNAPSHOT_EXCLUDE_EXISTING_DEPLOYMENTS = (
    "Restore without recreating the currently existing deployments"
)
FORCE_RESTORE_ON_DIRTY_MANAGER = (
    "Restore a snapshot on a manager where there are existing blueprints or "
    "deployments"
)
INCLUDE_METRICS_IN_SNAPSHOT = "Include metrics data in the snapshot"
EXCLUDE_CREDENTIALS_IN_SNAPSHOT = "Exclude credentials in the snapshot"
SNAPSHOT_ID = "The unique identifier for the snapshot"

KEEP_UP_ON_FAILURE = "Do not teardown the manager even if the bootstrap fails"
VALIDATE_ONLY = (
    "Only perform resource creation validation without actually bootstrapping"
)
SKIP_BOOTSTRAP_VALIDATIONS = (
    "Bootstrap without validating resource creation prior to bootstrapping "
    "the manager"
)
SKIP_BOOTSTRAP_SANITY = \
    "Bootstrap without performing the post-bootstrap sanity test"
DEV_TASK_ARGS = "Arguments for the fabric task"

MAINTENANCE_MODE_WAIT = (
    "Wait until there are no running executions and automatically activate "
    "maintenance-mode"
)

FORCE_DELETE_PLUGIN = (
    "Delete the plugin even if there are deployments which are currently "
    "using it"
)

FORCE_RECOVER = "This is mandatory for performing the recovery"

FORCE_TEARDOWN = "This is mandatory for performing the teardown"

IGNORE_DEPLOYMENTS = \
    "Teardown even if there are existing deployments on the manager"

TAIL_OUTPUT = "Tail the events of the specified execution until it ends"


SET_MANAGEMENT_CREDS = (
    'You can use the `-u` and `-k` flags to set the user and '
    'key-file path respectively. '
    '(e.g. `cfy use -u my_user -k ~/my/key/path`)'
)

DEFAULT_MUTUALITY_MESSAGE = 'Cannot be used simultaneously'

PROFILE_ALIAS = (
    'An alias to assign to the profile. This allows you to use '
    '`cfy use PROFILE_ALIAS` on top of `cfy use MANAGER_IP`'
)

MANAGEMENT_IP = 'The IP of the host machine on which you bootstrapped'
MANAGEMENT_USER = 'The user on the host machine with which you bootstrapped'
MANAGEMENT_KEY = 'The path to the ssh key-file to use when connecting'
MANAGEMENT_PORT = 'The port to use when connecting to the manager'
REST_PORT = "The REST server's port"

EXPORT_SSH_KEYS = 'Include ssh key files in archive'
IMPORT_SSH_KEYS = 'WARNING: Import exported keys to their original locations'

SORT_BY = "Key for sorting the list"
DESCENDING = "Sort list in descending order [default: False]"
