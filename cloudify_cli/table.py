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
from datetime import datetime

from .logger import get_logger

from prettytable import PrettyTable

from cloudify_rest_client.responses import ListResponse


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

    def get_values_per_column(column, row_data):
        if column in row_data:
            if row_data[column] and isinstance(row_data[column], basestring):
                row_data[column] = get_timestamp(row_data[column]) \
                                   or row_data[column]
            elif row_data[column] and isinstance(row_data[column], list):
                row_data[column] = ','.join(row_data[column])
            elif isinstance(row_data[column], bool):
                pass  # Taking care of False (otherwise would be changed to '')
            elif not row_data[column]:
                # if it's empty list, don't print []
                row_data[column] = ''
            return row_data[column]
        else:
            return defaults.get(column)

    pt = PrettyTable([labels.get(col, col) for col in cols])

    for d in data:
        values_row = []
        for c in cols:
            values_row.append(get_values_per_column(c, d))
        pt.add_row(values_row)

    return pt


def log(title, tb):
    logger = get_logger()
    logger.info('{0}{1}{0}{2}{0}'.format(os.linesep, title, tb))


def print_data(columns, items, header_text, max_width=None, defaults=None,
               labels=None):
    if items is None:
        items = []
    elif not isinstance(items, (list, ListResponse)):
        items = [items]

    pt = generate(columns, data=items, defaults=defaults, labels=labels)
    if max_width:
        pt.max_width = max_width
    log(header_text, pt)


def print_details(data, title):
    logger = get_logger()
    logger.info(title)

    for item in data.items():
        field_name = str(item[0]) + ':'
        field_value = str(item[1])
        field_value = get_timestamp(field_value) or field_value
        logger.info('{0} {1}'.format(field_name.ljust(15), field_value))


def get_timestamp(data):
    try:
        datetime.strptime(data[:10], '%Y-%m-%d')
        return data.replace('T', ' ').replace('Z', ' ')
    except ValueError:
        # not a timestamp
        return None
