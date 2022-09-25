import tempfile
from unittest.mock import Mock, patch

import pytest
from path import Path

from ravel import exceptions, loaders


@pytest.fixture
def tempdir():
    _tempdir = Path(tempfile.mkdtemp())
    yield _tempdir
    _tempdir.rmtree()


@pytest.fixture
def fs_loader(tempdir):
    return loaders.FileSystemLoader(base_path=tempdir)


class TestBaseLoader:
    def test_get_source_should_raise_not_implemented(self):
        loader = loaders.BaseLoader()
        with pytest.raises(NotImplementedError):
            loader.load(Mock(), Mock())


class TestGetUpToDateChecker:
    def test_it_should_return_an_up_to_date_checker(self, tempdir, fs_loader):
        fp = tempdir / "test.txt"
        fp.touch()
        with patch("os.path.getmtime") as getmtime:
            getmtime.return_value = 42.0
            is_up_to_date = fs_loader.get_up_to_date_checker(fp)
            assert is_up_to_date() is True

        fp.write_text("foo")
        assert is_up_to_date() is False

    def test_it_should_return_an_up_to_date_checker_that_fails_for_non_existent_file(
        self, tempdir, fs_loader
    ):
        fp = tempdir / "foo.txt"
        is_up_to_date = fs_loader.get_up_to_date_checker(fp)
        assert is_up_to_date() is False


class TestGetSource:
    def test_it_should_return_the_file_source_and_up_to_date_checker(
        self, tempdir, fs_loader
    ):
        env = Mock()
        (tempdir / "test.ravel").write_text("test!")
        with patch("os.path.getmtime") as getmtime:
            getmtime.return_value = 42.0
            result, is_up_to_date = fs_loader.get_source(env, "test")
            assert result == "test!"
            assert is_up_to_date() is True

        assert is_up_to_date() is False

    def test_it_should_raise_when_getting_source_of_nonexistent_rulebook(
        self, tempdir, fs_loader
    ):
        env = Mock()
        with pytest.raises(exceptions.RulebookNotFound):
            fs_loader.get_source(env, "foo")


class TestLoad:
    def test_it_should_load_and_compile_a_rulebook(self, tempdir, fs_loader):
        env = Mock()
        env.compile_rulebook.return_value = "compiled"
        checker = Mock(return_value=True)
        fs_loader.get_up_to_date_checker = Mock(return_value=checker)
        (tempdir / "test.ravel").write_text("test!")

        result = fs_loader.load(env, "test")
        assert result == "compiled"

        env.compile_rulebook.assert_called_once_with("test!", "test", checker)
