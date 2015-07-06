########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from contextlib import contextmanager

from colorama import Fore, Style

from cloudify.event import Event


class ColorfulEvent(Event):

    TIMESTAMP_COLOR = Fore.BLUE
    LOG_TYPE_COLOR = Fore.YELLOW
    EVENT_TYPE_COLOR = Fore.MAGENTA
    DEPLOYMENT_ID_COLOR = Fore.CYAN
    OPERATION_INFO_COLOR = Fore.GREEN
    NODE_ID_COLOR = Fore.BLUE
    SOURCE_ID_COLOR = Fore.BLUE
    TARGET_ID_COLOR = Fore.BLUE
    OPERATION_COLOR = Fore.YELLOW

    # colors entire message part according to event type
    _message_color_by_event_type = {
        'workflow_started': Style.BRIGHT + Fore.GREEN,
        'workflow_succeeded': Style.BRIGHT + Fore.GREEN,
        'workflow_failed': Style.BRIGHT + Fore.RED,
        'workflow_cancelled': Style.BRIGHT + Fore.YELLOW,

        'sending_task': Fore.MAGENTA,
        'task_started': Fore.MAGENTA,
        'task_succeeded': Fore.GREEN,
        'task_rescheduled': Fore.YELLOW,
        'task_failed': Fore.RED
    }

    # colors only the log level part
    _log_level_to_color = {
        'INFO': Fore.CYAN,
        'WARN': Fore.YELLOW,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'FATAL': Fore.RED
    }

    def __init__(self, event):
        super(ColorfulEvent, self).__init__(event)
        self._color_context = Fore.RESET + Style.RESET_ALL

    def get_operation_info(self):
        color = self.OPERATION_INFO_COLOR

        with self._nest_colors(color):
            op_info = super(ColorfulEvent, self).get_operation_info()

        return self._color_message(op_info, color)

    @property
    def text(self):
        event_type = super(ColorfulEvent, self).event_type  # might be None
        color = self._message_color_by_event_type.get(event_type)

        with self._nest_colors(color):
            msg = super(ColorfulEvent, self).text

        return self._color_message(msg, color)

    @property
    def timestamp(self):
        return self._color_message(super(ColorfulEvent, self).timestamp,
                                   self.TIMESTAMP_COLOR)

    @property
    def log_level(self):
        lvl = super(ColorfulEvent, self).log_level
        color = self._log_level_to_color.get(lvl)
        return self._color_message(lvl, color)

    @property
    def event_type_indicator(self):
        indicator = super(ColorfulEvent, self).event_type_indicator
        color = self.LOG_TYPE_COLOR if self.is_log_message else \
            self.EVENT_TYPE_COLOR
        return self._color_message(indicator, color)

    @property
    def operation(self):
        return self._color_message(super(ColorfulEvent, self).operation,
                                   self.OPERATION_COLOR)

    @property
    def node_id(self):
        return self._color_message(super(ColorfulEvent, self).node_id,
                                   self.NODE_ID_COLOR)

    @property
    def source_id(self):
        return self._color_message(super(ColorfulEvent, self).source_id,
                                   self.SOURCE_ID_COLOR)

    @property
    def target_id(self):
        return self._color_message(super(ColorfulEvent, self).target_id,
                                   self.TARGET_ID_COLOR)

    @property
    def deployment_id(self):
        return self._color_message(super(ColorfulEvent, self).deployment_id,
                                   self.DEPLOYMENT_ID_COLOR)

    @contextmanager
    def _nest_colors(self, nesting_color):
        prev_color_context = self._color_context
        if nesting_color:
            self._color_context = nesting_color
        yield
        self._color_context = prev_color_context

    def _color_message(self, val, color):
        if val is None or color is None:
            return val

        return "{0}{1}{2}".format(
            color,
            val,
            self._color_context)
