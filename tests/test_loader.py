import tempfile
import time

from unittest import TestCase
from unittest.mock import Mock, patch

from path import Path

from .helpers import ensure

from ravel import exceptions
from ravel import loaders


class BaseLoaderTests(TestCase):
    def test_get_source_should_raise_not_implemented(self):
        loader = loaders.BaseLoader()
        (ensure(loader.load)
         .called_with(Mock(), Mock())
         .raises(NotImplementedError))


class FileSystemLoaderTests(TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.loader = loaders.FileSystemLoader(base_path=self.tempdir)

    def tearDown(self):
        self.tempdir.rmtree()


class GetUpToDateCheckerTests(FileSystemLoaderTests):
    def test_it_should_return_an_up_to_date_checker(self):
        fp = self.tempdir / 'test.txt'
        fp.touch()
        with patch('os.path.getmtime') as getmtime:
            getmtime.return_value = 42.0
            is_up_to_date = self.loader.get_up_to_date_checker(fp)
            ensure(is_up_to_date()).is_true()

        fp.write_text('foo')
        ensure(is_up_to_date()).is_false()

    def test_it_should_return_an_up_to_date_checker_that_fails_for_non_existent_file(self):
        fp = self.tempdir / 'foo.txt'
        is_up_to_date = self.loader.get_up_to_date_checker(fp)
        ensure(is_up_to_date()).is_false()


class GetSourceTests(FileSystemLoaderTests):
    def test_it_should_return_the_file_source_and_up_to_date_checker(self):
        env = Mock()
        (self.tempdir / 'test.ravel').write_text('test!')
        with patch('os.path.getmtime') as getmtime:
            getmtime.return_value = 42.0
            result, is_up_to_date = self.loader.get_source(env, 'test')
            ensure(result).equals('test!')
            ensure(is_up_to_date()).is_true()

        ensure(is_up_to_date()).is_false()

    def test_it_should_raise_when_getting_source_of_nonexistent_rulebook(self):
        env = Mock()
        (ensure(self.loader.get_source)
         .called_with(env, 'foo')
         .raises(exceptions.RulebookNotFound))


class LoadTests(FileSystemLoaderTests):
    def test_it_should_load_and_compile_a_rulebook(self):
        env = Mock()
        env.compile_rulebook.return_value = 'compiled'
        checker = Mock(return_value = True)
        self.loader.get_up_to_date_checker = Mock(return_value=checker)
        (self.tempdir / 'test.ravel').write_text('test!')

        result = self.loader.load(env, 'test')
        ensure(result).equals('compiled')

        env.compile_rulebook.assert_called_once_with('test!', 'test', checker)
