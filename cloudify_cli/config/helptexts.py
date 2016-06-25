INPUTS_PARAMS_USAGE = """(Can be provided as wildcard based paths
 (*.yaml, /my_inputs/, etc..) to YAML files, a JSON string or as
 key1=value1;key2=value2). This argument can be used multiple times."""
WORKFLOW_TO_EXECUTE = "The workflow to execute (default: {0})"

BLUEPRINT_PATH = "The path to the application's blueprint file"
VALIDATE_BLUEPRINT = "Validate the blueprint"
RESET_CONFIG = "Reset the working environment"
SKIP_LOGGING = "Initialize quietly"
OUTPUT_PATH = "The local path to download to"
BLUEPRINT_FILENAME = \
    "The name of the archive's main blueprint file. (default: blueprint.yaml)"
INPUTS = "Inputs for the deployment {0}".format(INPUTS_PARAMS_USAGE)
PARAMETERS = "Parameters for the workflow {0}".format(INPUTS_PARAMS_USAGE)
ALLOW_CUSTOM_PARAMETERS = """Allow passing custom parameters (which were not
 defined in the workflow's schema in the blueprint) to the execution"""
INSTALL_PLUGINS = "Install the necessary plugins for the given blueprint"
EXECUTE_DEFAULT_INSTALL_WORKFLOW = WORKFLOW_TO_EXECUTE.format('uninstall')
EXECUTE_DEFAULT_UNINSTALL_WORKFLOW = WORKFLOW_TO_EXECUTE.format('install')
TASK_RETRIES = "How many times should a task be retried in case of failure"
TASK_THREAD_POOL_SIZE = "The size of the thread pool to execute tasks in"

SSH_COMMAND = "Execute a command on the manager over SSH"
SSH_HOST_SESSION = "Host an SSH tmux session"
SSH_CONNECT_TO_SESSION = "Join an SSH tmux session"
SSH_LIST_SESSIONS = "List available SSH tmux sessions"

OPERATION_TIMEOUT = """Operation timeout in seconds (The execution itself will keep
 going, but the CLI will stop waiting for it to terminate)"""
INCLUDE_LOGS = "Include logs in returned events"
JSON_OUTPUT = "Output events in a consumable JSON format"

SKIP_INSTALL = "Skip install lifecycle operations"
SKIP_UNINSTALL = "Skip uninstall lifecycle operations"
FORCE_UPDATE = """Force running update in case a previous
 update on this deployment has failed to finished successfully"""

DEPLOYMENT_ID = "The unique identifier for the deployment"
IGNORE_LIVE_NODES = """Delete the deployment even if there are existing live
 nodes for it"""

INCLUDE_SYSTEM_WORKFLOWS = "Include executions of system workflows"

FORCE_CONCURRENT_EXECUTION = """Execute the workflow even if there is an ongoing
 execution for the given deployment"""
FORCE_CANCEL_EXECUTION = """Terminate the execution abruptly, rather than request
 an orderly termination"""

INIT_LOCAL = "Initialize environment for local executions"
NODE_NAME = "The node's name"

FORCE_PURGE_LOGS = "Force purge. This flag is mandatory"
BACKUP_LOGS_FIRST = "Whether to backup before purging"

RESTORE_SNAPSHOT_EXCLUDE_EXISTING_DEPLOYMENTS = """Restore without recreating
 the currently existing deployments"""
FORCE_RESTORE_ON_DIRTY_MANAGER = """Restore a snapshots on a manager where
 there are existing blueprints or deployments"""
INCLUDE_METRICS_IN_SNAPSHOT = "Include metrics data in the snapshot"
EXCLUDE_CREDENTIALS_IN_SNAPSHOT = "Exclude credentials in the snapshot"
SNAPSHOT_ID = "The unique identifier for the snapshot"
