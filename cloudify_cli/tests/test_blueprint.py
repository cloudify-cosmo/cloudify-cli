from testtools import TestCase
from testtools.matchers import Equals

from cloudify_cli.blueprint import get


class TestGet(TestCase):
    """Test get a blueprint."""

    def test_url(self):
        """URLs are passed as they are to the manager."""
        urls = ['http://example.com', 'https://example.com']

        for url in urls:
            self.assertThat(get(url), Equals(url))
