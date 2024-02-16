VERBOSE = \
    "Show verbose output. You can supply this up to three times (i.e. -vvv)"
QUIET = "Show only critical logs"
VERSION = (
    "Display the version and exit (if a manager is used, its version will "
    "also show)"
)
EXTENDED_VIEW = "Display results in a vertical table format"

INPUTS_PARAMS_USAGE = (
    '(Can be provided as wildcard based paths '
    '(*.yaml, /my_inputs/, etc..) to YAML files, a JSON string or as '
    '\'key1=value1;key2=value2\'). This argument can be used multiple times'
)
WORKFLOW_TO_EXECUTE = "The workflow to execute [default: {0}]"

BLUEPRINT_PATH = "The path to the application's blueprint file."
BLUEPRINT_ID = "The unique identifier for the blueprint"
VALIDATE_BLUEPRINT = "Validate the blueprint first"

RESET_CONTEXT = "Reset the working environment"
HARD_RESET = "Hard reset the configuration, including coloring and loggers"
SHOW_ACTIVE_CONNECTION_INFORMATION = \
    "Show connection information for the active manager"
ENABLE_COLORS = "Enable colors in logger (use --hard when working with" \
                " an initialized environment) [default: False]"

OUTPUT_PATH = "The local path to download to."
INPUT_PATH = 'The local path to download from.'
IMPORT_SECRETS = 'The local path to the secrets file. ' \
                 'The secrets file should be a json format, i.e:\n' \
                 '[\n'\
                 '{\n'\
                 '\"key\":\"key\",\n'\
                 '\"value\":\"value\",\n'\
                 '\"tenant_name\":\"tenant_name\",\n'\
                 '\"visibility\":\"tenant\",\n'\
                 '\"is_hidden_value\": false,\n'\
                 '\"encrypted\": false\n'\
                 '}\n'\
                 ']'

OVERRIDE_COLLISIONS = 'If a certain key already exists in the destination' \
                      ' manager, its value will be updated with the new' \
                      ' imported value.'
TENANT_MAP = 'The path to a json file containing a dictionary of' \
             ' (source_tenant : destination_tenant) pairs. i.e:\n' \
             '{\"source_tenant\":\"destination_tenant\"}'
ALL_NODES = "Perform operation on all cluster nodes"
BLUEPRINT_FILENAME = (
    "The name of the archive's main blueprint file. "
    "This is only relevant if uploading an archive")
BLUEPRINT_ICON_PATH = "The path to the blueprint's icon file (must be a " \
                      "valid image in PNG format); the file will be saved " \
                      "as `icon.png` in the blueprint's resources and will "\
                      "overwrite any existing file with that name"
INPUTS = "Inputs for the deployment {0}".format(INPUTS_PARAMS_USAGE)
RUNTIME_PROPERTIES = "Runtime properties to be changed for the node " \
                     "instance {0}".format(INPUTS_PARAMS_USAGE)
PARAMETERS = "Parameters for the workflow {0}".format(INPUTS_PARAMS_USAGE)
REINSTALL_LIST = (
    "Node instances ids to be reinstalled as part of deployment update. They "
    "will be reinstalled even if the flag --skip-reinstall has been supplied"
)
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
SKIP_REINSTALL = (
    "Skip automatically reinstall node-instances that their properties has "
    "been modified, as part of a deployment update. Node instances that were "
    "explicitly given to the reinstall list will still be reinstalled"
)
SKIP_DRIFT_CHECK = "Skip running check_drift during deployment update"
FORCE_REINSTALL = "Reinstall all changed nodes, don't run update operations"
SKIP_HEAL = "Skip running heal and check_status before the update"
DONT_SKIP_REINSTALL = (
    "Reinstall node-instances that their properties have been modified as part"
    " of a deployment update. Node instances that were explicitly specified"
    " in the reinstall list will be reinstalled too."
)
IGNORE_FAILURE = (
    "Supply the parameter `ignore_failure` with the value `true` to the "
    "uninstall workflow"
)
INSTALL_FIRST = (
    "In deployment update, perform install workflow and then uninstall "
    "workflow. default: uninstall and then install"
)
PREVIEW = (
    "Preview the deployment update, stating what changes will be made "
    "without actually applying any changes."
)
DONT_UPDATE_PLUGINS = (
    "Don't update the plugins."
)

FORCE_UPDATE = (
    "Force running the update also in case a deployment is used as a component"
)
FORCE_PLUGINS_UPDATE = (
    "Force running the update also in case a blueprint (for which the update "
    "is executed) is used as a component"
)

DEPLOYMENT_ID = "The unique identifier for the deployment"
EXECUTION_ID = "The unique identifier for the execution"
INCLUDE_SYSTEM_WORKFLOWS = "Include executions of system workflows"

FORCE_DELETE_DEPLOYMENT = (
    "Delete the deployment even if there are existing live nodes for it, "
    "or existing installations which depend on it"
)
FORCE_CONCURRENT_EXECUTION = (
    "Execute the workflow even if there is an ongoing execution for the given "
    "deployment"
)
FORCE_CANCEL_EXECUTION = (
    "Terminate the execution abruptly, rather than request an orderly "
    "termination"
)
KILL_EXECUTION = (
    "Terminate the execution abruptly, and also stop currently running tasks. "
    "This will stop all processes running operations and workflows for the "
    "given execution."
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
EXCLUDE_CREDENTIALS_IN_SNAPSHOT = "Exclude credentials from the snapshot"
EXCLUDE_LOGS_IN_SNAPSHOT = "Exclude logs from the snapshot"
EXCLUDE_EVENTS_IN_SNAPSHOT = "Exclude events from the snapshot"
SNAPSHOT_ID = "The unique identifier for the snapshot"

MAINTENANCE_MODE_WAIT = (
    "Wait until there are no running executions and automatically activate "
    "maintenance-mode"
)

FORCE_DELETE_PLUGIN = (
    "Delete the plugin even if there are deployments which are currently "
    "using it"
)

FORCE_DELETE_BLUEPRINT = (
    "Delete the blueprint regardless of it's state and even if there are "
    "deployments which are currently using it"
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

ASYNC_UPLOAD = (
    "Don't wait for the upload workflow to finish. Upload state can be "
    "checked at any time using the `cfy blueprints get` or `cfy "
    "blueprints list` commands."
)

PROFILE_MANAGER_IP = 'The address of the Manager'
SSH_USER = 'The SSH user on the manager host machine'
SSH_KEY = 'The path to the ssh key-file to use when connecting'
SSH_PORT = 'The SSH port to use when connecting to the manager'
MANAGER_TOKEN = 'Manager token used to run commands on the manager'
MANAGER_USERNAME = 'Manager username used to run commands on the manager'
MANAGER_PASSWORD = 'Manager password used to run commands on the manager'
MANAGER_TENANT = 'The tenant associated with the current user operating the ' \
                 'manager'
SSL_STATE = 'Required SSL state (on/off)'
REST_PORT = "The REST server's port"
SSL_REST = "Connect to REST server using SSL"
REST_CERT = "The REST server's external certificate file location (implies " \
    "--ssl)"
KERBEROS_ENV = "Whether or not to use kerberos while connecting to the manager"

EXPORT_SSH_KEYS = 'Include ssh key files in archive'
IMPORT_SSH_KEYS = 'WARNING: Import exported keys to their original locations'

SORT_BY = "Key for sorting the list"
DESCENDING = "Sort list in descending order [default: False]"
SEARCH = 'Search resources by id. The returned list will include only ' \
         'resources that contain the given search pattern'

TENANT = 'The name of the tenant'
TENANT_TEMPLATE = 'The name of the tenant of the {0}'
TENANT_LIST_TEMPLATE = 'The name of the tenant to list {0}s from'
ALL_TENANTS = 'Include resources from all tenants associated with the user. ' \
              'You cannot use this argument with arguments: [tenant_name].'
ALL_EXECUTIONS = 'Apply to all available executions'
GROUP = 'The name of the user group'
GROUP_DN = 'The ldap group\'s distinguished name. This option is required ' \
           'when using ldap'
GROUP_TENANT_ROLE = (
    'Role assigned to the users of group in the context of the tenant.'
)

SECURITY_ROLE = "A role to determine the user's permissions on the manager, " \
                "if admin or default (default: default role)"
PASSWORD = 'Cloudify manager password'

ENCRYPTION_PASSPHRASE = 'The passphrase used to encrypt or decrypt the ' \
                        'secrets` values, must be 8 characters long.'

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
LDAP_SERVER = (
    'The LDAP server address to authenticate against. '
    'Should be prefixed with the protocol and include the port, '
    'e.g. ldap://192.0.2.1:389 or ldaps://192.0.2.45:636'
)
LDAP_USERNAME = 'LDAP username to bind with. If not set, binds will '\
                'be performed using the credentials of the user attempting '\
                'to log in. If this is set, the --ldap-password option must '\
                'also be set.'
LDAP_PASSWORD = 'LDAP password to bind with. See ldap username for details.'
LDAP_DOMAIN = 'The LDAP domain to be used by the server'
LDAP_IS_ACTIVE_DIRECTORY = 'Specify whether the LDAP used for authentication' \
                           ' is Active-Directory.'
LDAP_DN_EXTRA = 'Extra LDAP DN options. '\
                '(deprecated, use --ldap-base-dn instead)'
LDAP_CA_PATH = (
    'Path to the CA certificate LDAP communications will be encrypted with. '
    'Required if using ldaps. '
    'Must not be provided if not using ldaps.'
)
LDAP_BASE_DN = (
    'The base DN for searches, etc. If not provided, this will be derived '
    'from the domain used, e.g. a domain of example.com will result in a '
    'base dn of dc=example,dc=com'
)
LDAP_GROUP_DN = (
    'The base DN for searching for groups when performing user group '
    'lookups. This will only be used if the group membership is not '
    'available on the user object.'
)
LDAP_BIND_FORMAT = (
    'The format to use when binding to the LDAP server.'
)
LDAP_USER_FILTER = (
    'The search filter when searching for the LDAP user.'
)
LDAP_GROUP_MEMBER_FILTER = (
    'The filter used when searching recursively for group membership.'
)
LDAP_ATTRIBUTE_EMAIL = \
    "The name of the ldap attribute giving the user's email address."
LDAP_ATTRIBUTE_FIRST_NAME = \
    "The name of the ldap attribute giving the user's first name."
LDAP_ATTRIBUTE_LAST_NAME = \
    "The name of the ldap attribute giving the user's last name."
LDAP_ATTRIBUTE_UID = "The name of the ldap attribute giving the user's uid."
LDAP_ATTRIBUTE_GROUP_MEMBERSHIP = \
    "The name of the ldap attribute giving the user's group membership."
LDAP_NESTED_LEVELS = (
    "How many levels of group membership to check to find the groups the "
    "LDAP user is in. If set to 1 (the default), only the groups the user "
    "is directly a member of will be available."
)

GET_DATA = 'When set to True, displays the full list of connected resources ' \
           '(users/tenants/user-groups), for each listed resource. When set ' \
           'to False displays the total number of connected resources. ' \
           '(default:False)'
PROFILE_NAME = 'Name of the profile to use'
SECRET_VALUE = "The secret's value to be set"
SECRET_STRING = "The string to use as the secret's value"
SECRET_FLAG_DICT = "Whether the secret is to be treated as a dict"
SECRET_FLAG_LIST = "Whether the secret is to be treated as a lists"
SECRET_SCHEMA = "A JSON schema against which the secret will be validated [" \
                "default: '{\"type\": \"string\"}']"
SECRET_FILE = "The file with the contents of the secret"
SECRET_UPDATE_IF_EXISTS = 'Update secret value if secret key already ' \
                          'exists. [This option is deprecated; use cfy ' \
                          'secrets update command instead]'
HIDDEN_VALUE = 'The secret value is only shown to the user that created the ' \
               'secret and to admins. Use of the secret is allowed ' \
               'according to user roles and the visibility of the secret'
PLUGINS_BUNDLE_PATH = 'The path of the plugins bundle'
CLUSTER_NODE_OPTIONS = 'Additional options for the cluster node '\
                       'configuration {0}'.format(INPUTS_PARAMS_USAGE)
PRIVATE_RESOURCE = 'This option is deprecated; use --visibility option ' \
                   'instead. If set to True the uploaded resource will only ' \
                   'be accessible by its creator. Otherwise, the resource ' \
                   'is accessible by all users that belong to the same ' \
                   'tenant [default: False].'
VISIBILITY = 'Defines who can see the resource, can be set to one of {0}'
VISIBILITY_FILTER = 'Filters the secrets exported according to their' \
                    ' visibility, can be set to one of the following {0}.'
FILTER_BY_KEYWORD = 'Filters the secrets exported according to a keyword.'
PLUGIN_YAML_PATH = "The path to the plugin's yaml file"
PLUGIN_ICON_PATH = "The path to the plugin's icon file (must be a valid " \
                   "PNG image)"
PLUGIN_TITLE = "The plugins title used e.g. in UI for presentation purposes " \
               "in Topology widget."
PAGINATION_SIZE = 'The max number of results to retrieve per page ' \
                  '[default: 1000]'
PAGINATION_OFFSET = 'The number of resources to skip; --pagination-offset=1 ' \
                    'skips the first resource [default: 0]'
DRY_RUN = 'If set, no actual operations will be performed. This ' \
          'only prints the executed tasks, without side effects'

MANAGER_IP = "The private IP of the current leader (master) Manager. This " \
             "IP is used to connect to the Manager's RabbitMQ. " \
             "(relevant only in HA cluster)"
MANAGER_CERTIFICATE_PATH = 'A path to a file containing the SSL certificate ' \
                           'of the current leader Manager. The certificate ' \
                           'is available on the Manager: ' \
                           '/etc/cloudify/ssl/cloudify_internal_ca_cert.pem'
MANAGER_REST_TOKEN = 'The REST token of the new Cloudify Manager.' \
                     ' Acquire the token by running `cfy tokens get` while' \
                     ' using the new Manager.'
STOP_OLD_AGENT = 'If set, after installing the new agent the old agent ' \
                 '(that is connected to the old Cloudify Manager) will be ' \
                 'stopped. *IMPORTANT* if the deployment has monitoring ' \
                 'with auto-healing configured, you need to disable it first'
IGNORE_PLUGIN_FAILURE = 'If set, plugin installation errors during snapshot ' \
                        'restore will only be logged as warnings, and will ' \
                        'not fail the snapshot restore workflow'
QUEUE_SNAPSHOTS = 'If set, snapshot-creation-workflows that can`t currently ' \
                  'run will be queued and run automatically when possible'
QUEUE_LOG_BUNDLES = 'If set, log-bundle-creation-workflows that can`t ' \
                    'currently run will be queued and run automatically ' \
                    'when possible'
QUEUE_EXECUTIONS = 'If set, executions that can`t currently run will be '\
                   'queued and run automatically when possible'

TIME_UNITS = 'Supported time units are: min|minute(s)|h|hour(s)|d|day' \
             '(s)|w|week(s)|mo| month(s)|y|year(s)'

SCHEDULE_EXECUTIONS = 'This option is deprecated; use `cfy deployments ' \
                      'schedule create` instead. The time (including ' \
                      'timezone) this workflow will be executed at; ' \
                      'expected format: YYYYMMDDHHMM+HHMM or ' \
                      'YYYYMMDDHHMM-HHMM. e.g.: 201801182230-0500 (18th ' \
                      'January 2018 10:30pm EST)'

SCHEDULE_NAME = "A name for the schedule. If not provided, defaults to " \
                "{workflow-id}"
SCHEDULE_RECURRENCE = "Recurrence on the scheduled execution. e.g. " \
                     "'2 weeks', '30 min' or '1d'. " + TIME_UNITS
SCHEDULE_COUNT = "Maximum number of times to run the execution. " \
                 "If left empty, there's no limit on repetition"
SCHEDULE_WEEKDAYS = "Weekdays on which to run the execution, e.g. " \
                    "'su,mo,tu'. You can also prefix 1 to 4 or l-, e.g. " \
                    "'1su, l-fr' for running on the 1st Sunday and last " \
                    "Friday of a month. If left empty, will run on any weekday"
SCHEDULE_RRULE = "A scheduling rule in the iCalendar format, e.g. " \
                 "'RRULE:FREQ=DAILY;INTERVAL=3', which means run every 3 " \
                 "days"
SCHEDULE_SLIP = "Maximum time window after the target time has passed, " \
                "in which the scheduled execution can run " \
                "[in minutes, default=0]"
SCHEDULE_STOP_ON_FAIL = "Whether to stop scheduling the execution in case " \
                        "it failed"

_MULTIPLE_TIMES_FRAGMENT = ' (can be passed multiple times, ' \
                           'or comma-separated)'
AGENT_NODE_INSTANCE_ID = 'The node instance id to be used for filtering ' \
                         + _MULTIPLE_TIMES_FRAGMENT
AGENT_NODE_ID = 'The node id to be used for filtering' \
                + _MULTIPLE_TIMES_FRAGMENT
AGENT_INSTALL_METHOD = 'Only show agents installed with this install_method' \
                       + _MULTIPLE_TIMES_FRAGMENT
AGENT_DEPLOYMENT_ID = DEPLOYMENT_ID + _MULTIPLE_TIMES_FRAGMENT
AGENT_ALL_STATES = 'Show agents in all states, not only started ones'

AGENTS_WAIT = "Wait for agents operations to end, and show execution logs"
INSTALL_AGENT_TIMEOUT = "Agent installation timeout"
WAIT_AFTER_FAIL = 'When a task fails, wait this many seconds for ' \
                  'already-running tasks to return'
RESET_OPERATIONS = 'Reset operations in started state, so that they are '\
                   'run again unconditionally'
LOCATION = "The location of the site, expected format: latitude,longitude " \
           "such as 32.071072,34.787274"
NEW_NAME = "The new name of the {0}"
SITE_NAME = "Deployment's site name"
DETACH_SITE = "If set, detach the current site, making the deployment " \
              "siteless [default: False]"
WITH_LOGS = "If set, then the deployment's management workers logs are " \
            "deleted as well [default: False]"

NETWORKS = "Networks as a JSON string or as \'net1=ip1;net2=ip2\'. " \
           "This argument can be used multiple times."

PORT = "A non-default network port to use for this component."
NON_ENCRYPTED = "Use this flag for none encrypted secrets' values."
RAW_JSON = "If set, then output the manager status in a JSON format"
NODE_ID = "Cloudify's auto-generated node id. " \
          "Run `cfy_manager node get-id` on the node to retrieve it."

RUNTIME_ONLY_EVALUATION = "If set, all intrinsic functions will only be "\
                          "evaluated at runtime, and no intrinsic functions "\
                          "will be evaluated at parse time (such as "\
                          "get_input, get_property)"
AUTO_CORRECT_TYPES = "If set, before creating plan for a new deployment, an "\
                     "attempt will be made to cast old inputs' values to "\
                     "the valid types declared in blueprint"
MANAGER = "Connect to a specific manager by IP or host"

FROM_DATETIME = "Beginning of a period"
TO_DATETIME = "End of a period"

TIME_EXPRESSION = "{}. Supported formats: YYYY-MM-DD HH:MM, HH:MM, or a time" \
                  " delta expression such as '+2 weeks' or '+1day+10min'. " \
                  + TIME_UNITS
TIMEZONE = "The timezone to be used for scheduling, e.g. 'EST' or " \
           "'Asia/Jerusalem'. By default, the local timezone will be used. " \
           "Supports any timezone in the tz database (" \
           "en.wikipedia.org/wiki/List_of_tz_database_time_zones)"

BEFORE = "How long ago did the specified period ended"
KEEP_LAST = "Keep the N most recent {0} from deletion"

STORE_BEFORE_DELETION = "List and store events before deleting them"
STORE_OUTPUT_PATH = "Store listed events to a specified file (cli side)"

PLUGINS_UPDATE_ALL = "Iterate through all blueprints of the current tenant "\
                     "and update all used plugins"
PLUGINS_UPDATE_EXCEPT_BLUEPRINT = "List of blueprint IDs to be excluded "\
                                  "from all blueprints update (can be passed "\
                                  "multiple times or take comma separated "\
                                  "values)"
PLUGINS_UPDATE_NAME = "Update only the specific plugin in all selected "\
                      "deployments (can be passed multiple times or take "\
                      "comma separated values)"
PLUGINS_UPDATE_TO_LATEST = "List of plugin names to be upgraded to the "\
                           "latest version (can be passed multiple times "\
                           "or take comma separated values)"
PLUGINS_UPDATE_ALL_TO_LATEST = "Update all (selected) plugins to the latest "\
                               "version of a plugin"
PLUGINS_UPDATE__TO_MINOR = "List of plugin names to be upgraded to the "\
                           "latest minor version (can be passed multiple "\
                           "times or take comma separated values)"
PLUGINS_UPDATE_ALL_TO_MINOR = "Update all (selected) plugins to the latest "\
                              "minor version"
REEVALUATE_ACTIVE_STATUSES = "If set, before attempting to update, the " \
                             "statuses of previous active update " \
                             "operations will be reevaluated based on " \
                             "relevant executions' statuses.  `terminated` " \
                             "executions will be mapped to `successful` " \
                             "updates, while `failed` and any `*cancel*` " \
                             "statuses will be mapped to `failed`."
REEVALUATE_ACTIVE_STATUSES_PLUGINS = REEVALUATE_ACTIVE_STATUSES + "  This " \
                                     "flag is also passed down to the " \
                                     "deployment update flows and has " \
                                     "a similar effect on those."

LABELS = "A labels list of the form <key>:<value>,<key>:<value>. " \
         "Any comma and colon in <value> must be escaped with `\\`. " \
         "The labels' keys are saved in lowercase."

LABELS_FILTER_RULES = "A labels' filter rule. Labels' filter rules must be " \
                      "one of: <key>=<value>, <key>!=<value>, " \
                      "<key> is-not <value>, <key> is null, " \
                      "<key> is not null. <value> can be a single string or " \
                      "a list of strings of the form " \
                      "[<value1>,<value2>,...]. Any comma and " \
                      "colon in <value> must be escaped with `\\`. " \
                      "The labels' keys specified in the filter rules will " \
                      "be saved in lower case."

ATTRS_FILTER_RULES = "An attributes' filter rule. Attributes' filter rules " \
                     "must be one of: <key>=<value>, <key>!=<value>, " \
                     "<key> contains <value>, " \
                     "<key> does-not-contain <value>, " \
                     "<key> starts-with <value>, <key> ends-with <value>, " \
                     "<key> is not empty. <value> can be a single string or " \
                     "a list of strings of the form [<value1>,<value2>,...]." \
                     " Allowed attributes to filter by are: "

DEPLOYMENTS_ATTRS_FILTER_RULES = ATTRS_FILTER_RULES + \
                                 '[blueprint_id, created_by, site_name, ' \
                                 'schedules]. This argument can be used ' \
                                 'multiple times'

BLUEPRINTS_ATTRS_FILTER_RULES = ATTRS_FILTER_RULES + \
                                '[created_by]. This argument can be ' \
                                'used multiple times'

FILTER_ID = 'Filter results according to the specified filter'

DEP_GROUP_ID = 'Deployment group id (a name).'
DEP_GROUP_BLUEPRINT = 'Default blueprint for this deployment group'
DEP_GROUP_DESCRIPTION = 'Description of this deployment group'
DEP_GROUP_DEP_ID = 'Deployment ID to add or remove from the group'
DEP_GROUP_COUNT = 'Create this many deployments in the group'
DEP_GROUP_FILTER_ID = 'Use deployments selected by this filter'
DEP_GROUP_FROM_GROUP = 'Use deployments belonging to this group'
DEP_GROUP_INTO_ENVIRONMENTS = 'Add created deployments to the environments ' \
                              'already existing in this group.'
GROUP_ID_FILTER = 'Show only results belonging to this group'
DELETE_GROUP_DEPLOYMENTS = 'Delete all deployments belonging to this group'
EXECUTION_GROUP_CONCURRENCY = 'Run this many executions at a time'

GENERATE_ID = 'Generate a UUID to serve as the deployment ID. This flag ' \
              'cannot be provided if a deployment ID is specified'

DISPLAY_NAME = 'The display name of the deployment. If not specified, ' \
               'the deployment ID will be used instead.'

SEARCH_NAME = 'Search deployments by their display name. The returned list ' \
              'will include only deployments that contain the given search ' \
              'pattern'
DEPENDENCIES_OF = 'List only deployments on which the given deployment ID ' \
                  'depends.'
AUDIT_CREATOR_NAME = 'Name of a user who introduced changes recorded in the ' \
                     'audit log.'
AUDIT_EXECUTION_ID = 'ID of an execution which introduced changes recorded ' \
                     'in the audit log.'
AUDIT_SINCE = 'List audit logs starting from this timestamp.  Can be ' \
              'specified either as the difference counted from the current ' \
              'time (e.g. 6.5h for 6:30 hours ago, 2d - 2 days ago, 7w - 7 ' \
              'weeks ago), or an ordinary UTC timestamp (2021-08-18, ' \
              '2021-08-18T14:25:36, 2021-08-18 14:25:36, 2021-08-18 ' \
              '14:25:36.99, @1629296736).'
AUDIT_FOLLOW = 'Specify if the logs should be streamed.'
AUDIT_TRUNCATE_BEFORE = 'Truncate audit logs which were stored this long ' \
                        'ago or earlier.  Can be specified either as the ' \
                        'difference counted from the current time (e.g. ' \
                        '6.5h for 6:30 hours ago, 2d - 2 days ago, 7w - 7 '\
                        'weeks ago), or an ordinary UTC timestamp ' \
                        '(2021-08-18, 2021-08-18T14:25:36, 2021-08-18 '\
                        '14:25:36, 2021-08-18 14:25:36.99, @1629296736).'

SET_USERNAME = 'The name of the user who will be the new owner '\
               'of the resource.'
WORKER_NAMES = 'Show the worker name for each event'
DRIFT_ONLY = 'Run update without changing anything. This will still check ' \
             'drift and run update operations as necessary'
TEMPDIR_PATH = "Temporary location to be used for snapshot creation. If not " \
               "specified, /tmp will be used."
LEGACY_SNAPSHOT = "Create legacy version of the snapshot (as opposed to 'new')"
SNAPSHOT_LISTENER_TIMEOUT = "Changes the timeout for pending actions to " \
                           "complete. As snapshot creation is a " \
                           "non-blocking execution, it can be run " \
                           "independently of others. System changes " \
                           "occuring during snapshot creation are added " \
                           "to the snapshot. This parameter specified the " \
                           "additional waiting time (in seconds)."
WAIT_FOR_STATUS = "Whether to wait for snapshot status [default: False]."
SUMMARY_HELP = """
    Retrieve summary of {type}, e.g. a count of each {example}.

    `TARGET_FIELD` is the field to summarize {type} on. `SUB_FIELD` is an
    optional second field to summarize {type} on. Both can be chosen from
    [{fields}].

    E.g. `cfy {type} summary tenant_name visibility` will summarize
    {type} by tenant_name with a secondary grouping by visibility.
    """
SECRETS_PROVIDER_NAME = "Secrets Provider's name"
SECRETS_PROVIDER_NAME_MULTIPLE = "Secrets Provider's name list"
SECRETS_PROVIDER_SKIP_CHECK = "Do not check connectivity to secrets provider."
SECRETS_PROVIDER_TYPE = "Secrets Provider's type"
SECRETS_PROVIDER_CONNECTION_PARAMETERS = """
    Secrets Provider's connection parameters in stringify JSON format
    """
SECRETS_PROVIDER_OPTIONS = """
    Secrets Provider's options in stringify JSON format
    """
EVALUATE_FUNCTIONS = "Evaluate functions in returned nodes and node instances"
RECURSIVE_DELETE = 'Recursively delete all service deployments contained in ' \
                   'this deployment'
