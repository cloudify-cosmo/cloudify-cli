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
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import click

from dsl_parser.parser import parse_from_path
from dsl_parser.exceptions import DSLParsingException

from .. import utils
from ..config import cfy
from ..logger import get_logger
from ..exceptions import CloudifyCliError


@cfy.command(name='validate')
@click.argument('blueprint-path', required=True)
def validate(blueprint_path):
    """Validate a blueprint
    """
    logger = get_logger()
    logger.info('Validating blueprint: {0}'.format(blueprint_path))
    try:
        resolver = utils.get_import_resolver()
        validate_version = utils.is_validate_definitions_version()
        parse_from_path(
            dsl_file_path=blueprint_path,
            resolver=resolver,
            validate_version=validate_version)
    except DSLParsingException as ex:
        raise CloudifyCliError('Failed to validate blueprint {0}'.format(ex))
    logger.info('Blueprint validated successfully')
