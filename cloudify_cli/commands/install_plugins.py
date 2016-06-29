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

import click

from .. import common
from ..config import cfy


@cfy.command(name='install-plugins')
@click.argument('blueprint-path', required=True, type=click.Path(exists=True))
def install_plugins(blueprint_path):
    """Install the necessary plugins for a given blueprint
    """
    common.install_blueprint_plugins(blueprint_path=blueprint_path)
