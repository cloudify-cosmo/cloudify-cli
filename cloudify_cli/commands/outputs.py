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

import json

import click

from .. import utils
from .. import common
from ..logger import get_logger


@click.command(name='outputs', context_settings=utils.CLICK_CONTEXT_SETTINGS)
def outputs():
    """Display outputs for the execution
    """
    logger = get_logger()
    env = common.load_env()
    logger.info(json.dumps(env.outputs() or {}, sort_keys=True, indent=2))
