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

import os
import json
from datetime import datetime

from cloudify_cli.logger import (
    get_global_json_output,
    get_global_extended_view,
    CloudifyJSONEncoder,
    output)
from cloudify_cli.prettytable import PrettyTable


def generate(cols, data, defaults=None, labels=None):
    """
    Return a new PrettyTable instance representing the list.

    Arguments:

        cols - An iterable of strings that specify what
               are the columns of the table.

               for example: ['id','name']

        data - An iterable of dictionaries, each dictionary must
               have key's corresponding to the cols items.

               for example: [{'id':'123', 'name':'Pete']

        defaults - A dictionary specifying default values for
                   key's that don't exist in the data itself.

                   for example: {'deploymentId':'123'} will set the
                   deploymentId value for all rows to '123'.

        labels - A dictionary mapping a column name to a label that
                 will be used for the table header

    """
    defaults = defaults or {}
    labels = labels or {}
    pt = PrettyTable([labels.get(col, col) for col in cols])

    for d in data:
        values_row = []
        for c in cols:
            values_row.append(get_values_per_column(c, d, defaults))
        pt.add_row(values_row)

    return pt


def generate_extended(cols, data, defaults=None, labels=None):
    defaults = defaults or {}
    labels = labels or {}
    pt = PrettyTable(["Field", "Value"])
    pt.align["Field"] = "l"
    pt.align["Value"] = "l"
    for c in cols:
        display_value = get_values_per_column(c, data, defaults)
        pt.add_row([labels.get(c, c), display_value])
    return pt


def get_values_per_column(column, row_data, defaults):
    if column in row_data:
        if row_data[column] and isinstance(row_data[column], str):
            row_data[column] = get_timestamp(row_data[column]) \
                or row_data[column]
        elif row_data[column] and isinstance(row_data[column], list):
            row_data[column] = ','.join(row_data[column])
        elif isinstance(row_data[column], bool):
            pass  # Taking care of False (otherwise would be changed to '')
        elif isinstance(row_data[column], int):
            pass  # Taking care of zero (otherwise would be changed to '')
        elif not row_data[column]:
            # if it's empty list, don't print []
            row_data[column] = ''
        return row_data[column]
    else:
        return defaults.get(column, 'N/A')


def display(title, tb):
    output('{0}{1}{0}{2}{0}'.format(os.linesep, title, tb))


def format_json_object(cols, item, defaults=None, labels=None):
    defaults = defaults or {}
    labels = labels or {}

    return json.dumps({
        labels.get(col, col): item.get(col) if item.get(col) is not None
        else defaults.get(col)
        for col in cols
    }, cls=CloudifyJSONEncoder)


def format_json_output(cols, data, defaults=None, labels=None):
    # output the json array newline-separated to aid debuggability: makes
    # it possible to analyze the output line-by-line and use eg. grep
    output('[')
    output(',\n'.join(
        format_json_object(cols, item, defaults, labels) for item in data))
    output(']')


def print_data(columns, items, header_text, max_width=None, defaults=None,
               labels=None):
    """Display the items in a tabular manner.
    """
    if get_global_json_output():
        format_json_output(columns, items, defaults=defaults, labels=labels)
    elif get_global_extended_view():
        if not items:
            output("{0}[NO RECORDS]{0}".format(os.linesep))
        for i, entry in enumerate(items):
            pt = generate_extended(
                columns, data=entry, defaults=defaults, labels=labels)
            if max_width:
                pt.max_width = max_width
            display("{0} [RECORD {1}]".format(header_text, i+1), pt)
    else:
        pt = generate(columns, data=items, defaults=defaults, labels=labels)
        if max_width:
            pt.max_width = max_width
        display(header_text, pt)


def print_single(columns, item, header_text, max_width=None, defaults=None,
                 labels=None):
    """Print out a single item.

    This is similar to the table-generating print_data, but for use when
    it is known that there is only going to be one item.
    """
    if get_global_json_output():
        output(format_json_object(
            columns, item, defaults=defaults, labels=labels))
    elif get_global_extended_view():
        pt = generate_extended(
            columns, data=item, defaults=defaults, labels=labels)
        if max_width:
            pt.max_width = max_width
        display(header_text, pt)
    else:
        print_data(columns, [item], header_text, max_width, defaults, labels)


def print_list(data, title):
    """Print a bulleted list with a title"""
    output(title)
    for item in data:
        output('\t- {0}'.format(get_timestamp(str(item)) or item))


def print_details(data, title):
    """Utility for printing structured key/value pairs.

    Note that this is not for printing the standard output table, but
    rather for auxiliary data.
    """
    if get_global_json_output():
        output(json.dumps(data, cls=CloudifyJSONEncoder))
    else:
        output(title)
        if data and isinstance(data, dict):
            max_name_width = max(len(k) for k in data.keys()) + 5
            for item in data.items():
                field_name = str(item[0]) + ':'
                field_value = str(item[1])
                field_value = get_timestamp(field_value) or field_value
                output('\t{0} {1}'.format(field_name.ljust(max_name_width),
                                          field_value))


def get_timestamp(data):
    try:
        datetime.strptime(data[:10], '%Y-%m-%d')
        return data.replace('T', ' ').replace('Z', ' ')
    except ValueError:
        # not a timestamp
        return None
