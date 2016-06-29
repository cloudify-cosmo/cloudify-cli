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

import os

import click

from .. import utils
from .. import common
from .. import exceptions
from ..config import options
from ..logger import get_logger


@click.command(name='create-requirements')
@click.argument('blueprint-path', required=True, type=click.Path(exists=True))
@options.output_path
def create_requirements(blueprint_path, output_path):
    """Create a pip-compliant requirements file for a given blueprint
    """
    logger = get_logger()
    if output_path and os.path.exists(output_path):
        raise exceptions.CloudifyCliError(
            'Output path {0} already exists'.format(output_path))

    requirements = common.create_requirements(blueprint_path=blueprint_path)

    if output_path:
        utils.dump_to_file(requirements, output_path)
        logger.info('Requirements file created successfully --> {0}'
                    .format(output_path))
    else:
        # We don't want to use just logger
        # since we want this output to be prefix free.
        # this will make it possible to pipe the
        # output directly to pip
        for requirement in requirements:
            print(requirement)
            logger.info(requirement)
