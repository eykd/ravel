import tempfile
import time

from unittest import TestCase
from unittest.mock import Mock, patch

from path import Path

from .helpers import ensure

from ravel import environments
from ravel import loaders


PATH = Path(__file__).abspath().dirname()
EXAMPLES  = PATH.parent / 'examples'


class EnvironmentTests(TestCase):
    def setUp(self):
        self.env = environments.Environment(
            loader=loaders.FileSystemLoader(base_path=EXAMPLES / 'simple'),
        )


class LoadTests(EnvironmentTests):
    def test_it_should_load_the_initializing_rulebook(self):
        with patch.object(self.env, 'load_rulebook') as mock_loader:
            self.env.load()
            mock_loader.assert_called_once_with('begin')
            self.env.initializing_name = 'intro'
            mock_loader.reset_mock()
            self.env.load()
            mock_loader.assert_called_once_with('intro')


class GetRulebookTests(EnvironmentTests):
    def test_it_should_load_the_rulebook_and_its_includes(self):
        rulebook = self.env.load_rulebook('begin')
        (ensure(rulebook['rulebook']['Situation']['locations'])
         .contains('begin::intro'))
        (ensure(rulebook['rulebook']['Situation']['locations'])
         .contains('rooms::rooms'))
        (ensure(rulebook['rulebook']['Situation']['locations'])
         .contains('actions::actions'))

        new_rulebook = self.env.load_rulebook('begin')
        ensure(new_rulebook).equals(rulebook)


class DefaultIsUpToDateTests(EnvironmentTests):
    def test_it_should_return_true(self):
        ensure(self.env.default_is_up_to_date()).is_true()
