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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

# import cfy actions
from cloudify_cli.commands.version import VersionAction as version

# import cfy direct commands
from cloudify_cli.commands.dev import dev as dev
from cloudify_cli.commands.bootstrap import bootstrap as bootstrap
from cloudify_cli.commands.teardown import teardown as teardown
from cloudify_cli.commands.status import status as status
from cloudify_cli.commands.use import use as use
from cloudify_cli.commands.ssh import ssh as ssh
from cloudify_cli.commands.init import init as init

# import cfy sub commands
from cloudify_cli.commands import blueprints
from cloudify_cli.commands import deployments
from cloudify_cli.commands import events
from cloudify_cli.commands import executions
from cloudify_cli.commands import workflows