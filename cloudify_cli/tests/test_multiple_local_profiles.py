########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
import shutil

from .. import env
from . import cfy
from .commands.constants import (
    BLUEPRINTS_DIR,
    DEFAULT_BLUEPRINT_FILE_NAME,
)
from testtools import TestCase
from testtools.matchers import DirExists


class TestMultipleLocalProfiles(TestCase):

    """Verify that multple local profiles can be used."""

    LOCAL_BLUEPRINT_PATH = os.path.join(
        BLUEPRINTS_DIR,
        'local',
        DEFAULT_BLUEPRINT_FILE_NAME,
    )

    LOCAL_PROFILE_DIR = os.path.join(env.PROFILES_DIR, 'local')

    def tearDown(self):
        """Delete cloudify data directory."""
        super(TestMultipleLocalProfiles, self).tearDown()
        shutil.rmtree(env.CLOUDIFY_WORKDIR, ignore_errors=True)

    def test_default_blueprint_id(self):
        """Default blueprint id is the directory name."""
        cfy.invoke('init {0}'.format(self.LOCAL_BLUEPRINT_PATH))
        self.assertThat(
            os.path.join(self.LOCAL_PROFILE_DIR, 'local'),
            DirExists(),
        )

    def test_blueprint_id(self):
        """Blueprint id passed as argument is used."""
        cfy.invoke(
            'init -b my-blueprint {0}'.format(self.LOCAL_BLUEPRINT_PATH))
        self.assertThat(
            os.path.join(self.LOCAL_PROFILE_DIR, 'my-blueprint'),
            DirExists(),
        )

    def test_multiple_blueprints(self):
        """Multiple blueprints with different id can coexist."""
        blueprint_count = 5

        for blueprint_number in range(blueprint_count):
            cfy.invoke(
                'init -b my-blueprint-{0} {1}'
                .format(blueprint_number, self.LOCAL_BLUEPRINT_PATH)
            )
        for blueprint_number in range(blueprint_count):
            self.assertThat(
                os.path.join(
                    self.LOCAL_PROFILE_DIR,
                    'my-blueprint-{0}'.format(blueprint_number),
                ),
                DirExists(),
            )
