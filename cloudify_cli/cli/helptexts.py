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
EXECUTION_ID = "The unique identifier for the execution"
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
EXCLUDE_CREDENTIALS_IN_SNAPSHOT = "Exclude credentials from the snapshot"
EXCLUDE_LOGS_IN_SNAPSHOT = "Exclude logs from the snapshot"
EXCLUDE_EVENTS_IN_SNAPSHOT = "Exclude events from the snapshot"
SNAPSHOT_ID = "The unique identifier for the snapshot"

DEV_TASK_ARGS = "Arguments for the fabric task"

MAINTENANCE_MODE_WAIT = (
    "Wait until there are no running executions and automatically activate "
    "maintenance-mode"
)

FORCE_DELETE_PLUGIN = (
    "Delete the plugin even if there are deployments which are currently "
    "using it"
)

FORCE_TEARDOWN = "This is mandatory for performing the teardown"

IGNORE_DEPLOYMENTS = \
    "Teardown even if there are existing deployments on the manager"

TAIL_OUTPUT = "Tail the events of the specified execution until it ends"

SET_MANAGEMENT_CREDS = (
    'You can use the `-s` and `-k` flags to set the ssh user and '
    'key-file path respectively. '
    '(e.g. `cfy profiles use -s my_user -k ~/my/key/path`)'
)

MANAGEMENT_IP = 'The IP of the manager host machine'
SSH_USER = 'The SSH user on the manager host machine'
SSH_KEY = 'The path to the ssh key-file to use when connecting'
SSH_PORT = 'The SSH port to use when connecting to the manager'
MANAGER_USERNAME = 'Manager username used to run commands on the manager'
MANAGER_PASSWORD = 'Manager password used to run commands on the manager'
MANAGER_TENANT = 'The tenant associated with the current user operating the ' \
                 'manager'
SSL_STATE = 'Required SSL state (on/off)'
REST_PORT = "The REST server's port"
SSL_REST = "Connect to REST server using SSL"
REST_CERT = "The REST server's external certificate file location (implies " \
    "--ssl)"

EXPORT_SSH_KEYS = 'Include ssh key files in archive'
IMPORT_SSH_KEYS = 'WARNING: Import exported keys to their original locations'

SORT_BY = "Key for sorting the list"
DESCENDING = "Sort list in descending order [default: False]"

TENANT = 'The name of the tenant'
TENANT_TEMPLATE = 'The name of the tenant of the {0}'
TENANT_LIST_TEMPLATE = 'The name of the tenant to list {0}s from'
ALL_TENANTS = 'Include resources from all tenants associated with the user. ' \
              'You cannot use this argument with arguments: [tenant_name]'
GROUP = 'The name of the user group'
GROUP_DN = 'The ldap group\'s distinguished name. This option is required ' \
           'when using ldap'
GROUP_TENANT_ROLE = (
    'Role assigned to the users of group in the context of the tenant.'
)

SECURITY_ROLE = "A role to determine the user's permissions on the manager " \
                "(default: default)"
PASSWORD = 'Cloudify manager password'

CLUSTER_HOST_IP = \
    'The IP of this machine to use for advertising to the cluster'
CLUSTER_JOIN = 'Address of one of the cluster members to join'
CLUSTER_NODE_NAME = \
    'Name of this manager machine to be used internally in the cluster'
CLUSTER_JOIN_PROFILE = (
    'After joining the cluster, add the current manager to this profile '
    '(use when you have a profile containing the cluster master)'
)

SKIP_PLUGINS_VALIDATION = 'Determines whether to validate if the' \
                          ' required deployment plugins exist on the manager.'\
                          ' If validation is skipped, plugins containing' \
                          ' source URL will be installed from source.' \

USER = 'Username of user to whom the permissions apply. ' \
       'This argument can be used multiple times'
USER_TENANT_ROLE = 'Role assigned to user in the context of the tenant.'
RESTORE_CERTIFICATES = 'Restore the certificates from the snapshot, using ' \
                       'them to replace the current Manager certificates. ' \
                       'If the certificates` metadata (I.E: the Manager IP ' \
                       'address) from the snapshot does not match the ' \
                       'Manager metadata, the certificates cannot work on ' \
                       'this Manager and will not be restored. In the event ' \
                       'that the certificates have been restored, the ' \
                       'Manager will be automatically rebooted at the end ' \
                       'of the execution. To avoid automatic reboot, use ' \
                       'the flag `--no-reboot` (not recommended)'
NO_REBOOT = 'Do not perform an automatic reboot to the Manager VM after ' \
            'restoring certificates a from snapshot (not recommended). ' \
            'Only relevant if the `--restore-certificates` flag was supplied'
SKIP_CREDENTIALS_VALIDATION = 'Do not check that the passed credentials are ' \
                              'correct (default: False)'
LDAP_SERVER = 'The LDAP server address to authenticate against'
LDAP_USERNAME = 'The LDAP admin username to be set on the Cloudify manager'
LDAP_PASSWORD = 'The LDAP admin password to be set on the Cloudify manager'
LDAP_DOMAIN = 'The LDAP domain to be used by the server'
LDAP_IS_ACTIVE_DIRECTORY = 'Specify whether the LDAP used for authentication' \
                           ' is Active-Directory.'
LDAP_DN_EXTRA = 'Extra LDAP DN options.'

GET_DATA = 'When set to True, displays the full list of connected resources ' \
           '(users/tenants/user-groups), for each listed resource. When set ' \
           'to False displays the total number of connected resources. ' \
           '(default:False)'
PROFILE_NAME = 'Name of the profile to use'
SECRET_VALUE = "The secret's value to be set"
SECRET_STRING = "The string to use as the secret's value"
SECRET_FILE = "The secret's file to use its content as value to be set"
SECRET_UPDATE_IF_EXISTS = 'Update secret value if secret key already exists'
PLUGINS_BUNDLE_PATH = 'The path of the plugins bundle'
CLUSTER_NODE_OPTIONS = 'Additional options for the cluster node '\
                       'configuration {0}'.format(INPUTS_PARAMS_USAGE)
PRIVATE_RESOURCE = 'This option is deprecated; use --visibility option ' \
                   'instead. If set to True the uploaded resource will only ' \
                   'be accessible by its creator. Otherwise, the resource ' \
                   'is accessible by all users that belong to the same ' \
                   'tenant [default: False].'
VISIBILITY = 'Defines who can see the resource, can be set to one of {0}'
PLUGIN_YAML_PATH = "The path to the plugin's yaml file"
PAGINATION_SIZE = 'The max number of results to retrieve per page ' \
                  '[default: 1000]'
PAGINATION_OFFSET = 'The number of resources to skip; --pagination-offset=1 ' \
                    'skips the first resource [default: 0]'
