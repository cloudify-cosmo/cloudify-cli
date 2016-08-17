########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
import glob
import yaml

from .logger import get_logger
from.exceptions import CloudifyCliError


# TODO: Add test for inputs as JSON/YAML string
def inputs_to_dict(resources):
    """Returns a dictionary of inputs

    `resources` can be:
    - A list of files.
    - A single file
    - A directory containing multiple input files
    - A key1=value1;key2=value2 pairs string.
    - A string formatted as JSON/YAML.
    - Wildcard based string (e.g. *-inputs.yaml)
    """
    logger = get_logger()

    if not resources:
        return dict()

    parsed_dict = {}

    for resource in resources:
        logger.debug('Processing inputs source: {0}'.format(resource))
        # Workflow parameters always pass an empty dictionary. We ignore it
        if isinstance(resource, basestring):
            try:
                parsed_dict.update(_parse_single_input(resource))
            except CloudifyCliError:
                raise CloudifyCliError(
                    "Invalid input: {0}. It must represent a dictionary. "
                    "Valid values can be one of:\n "
                    "- A path to a YAML file\n "
                    "- A path to a directory containing YAML files\n "
                    "- A single quoted wildcard based path "
                    "(e.g. '*-inputs.yaml')\n "
                    "- A string formatted as JSON/YAML\n "
                    "- A string formatted as key1=value1;key2=value2".format(
                        resource))
    return parsed_dict


def _parse_single_input(resource):
    try:
        # parse resource as string representation of a dictionary
        return plain_string_to_dict(resource)
    except CloudifyCliError:
        input_files = glob.glob(resource)
        parsed_dict = dict()
        if os.path.isdir(resource):
            for input_file in os.listdir(resource):
                parsed_dict.update(
                    _parse_yaml_path(os.path.join(resource, input_file)))
        elif input_files:
            for input_file in input_files:
                parsed_dict.update(_parse_yaml_path(input_file))
        else:
            parsed_dict.update(_parse_yaml_path(resource))
    return parsed_dict


def _parse_yaml_path(resource):

    try:
        # if resource is a path - parse as a yaml file
        if os.path.isfile(resource):
            with open(resource) as f:
                content = yaml.load(f.read())
        else:
            # parse resource content as yaml
            content = yaml.load(resource)
    except yaml.error.YAMLError as e:
        raise CloudifyCliError("'{0}' is not a valid YAML. {1}".format(
            resource, str(e)))

    # Emtpy files return None
    content = content or dict()
    if not isinstance(content, dict):
        raise CloudifyCliError()

    return content


def plain_string_to_dict(input_string):
    input_string = input_string.strip()
    input_dict = {}
    mapped_inputs = input_string.split(';')
    for mapped_input in mapped_inputs:
        mapped_input = mapped_input.strip()
        if not mapped_input:
            continue
        split_mapping = mapped_input.split('=')
        try:
            key = split_mapping[0].strip()
            value = split_mapping[1].strip()
        except IndexError:
            raise CloudifyCliError(
                "Invalid input format: {0}, the expected format is: "
                "key1=value1;key2=value2".format(input_string))
        input_dict[key] = value
    return input_dict
