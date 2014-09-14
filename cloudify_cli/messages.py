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


FILE_NOT_FOUND = "Could not find file: {0}"

VALIDATING_BLUEPRINT = "Validating {0}"
VALIDATING_BLUEPRINT_FAILED = "Failed to validate blueprint {0}: {1}"
VALIDATING_BLUEPRINT_SUCCEEDED = "Blueprint validated successfully"

DOWNLOADING_BLUEPRINT = "Downloading blueprint '{0}' ..."
DOWNLOADING_BLUEPRINT_SUCCEEDED = \
    "Blueprint '{0}' has been downloaded successfully as '{1}'"

SSH_LINUX_NOT_FOUND = """ssh not found. Possible reasons:
1) You don't have ssh installed (try installing OpenSSH)
2) Your PATH variable is not configured correctly
3) You are running this command with Sudo which can manipulate \
environment variables for security reasons"""

SSH_WIN_NOT_FOUND = """ssh.exe not found. Are you sure you have it installed?
As alternative you can use PuTTY to ssh into the management server. \
Do not forget to convert your private key from OpenSSH format to \
PuTTY's format using PuTTYGen."""
