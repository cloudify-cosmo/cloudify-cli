INPUTS_PARAMS_USAGE = "bla bla"
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
EXECUTE_DEFAULT_INSTALL_WORKFLOW = "The workflow to execute (default: install)"
TASK_RETRIES = "How many times should a task be retried in case of failure"
TASK_THREAD_POOL_SIZE = "The size of the thread pool to execute tasks in"
