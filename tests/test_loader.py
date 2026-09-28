import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ravel import exceptions, loaders


@pytest.fixture
def tempdir():
    _tempdir = Path(tempfile.mkdtemp())
    yield _tempdir
    shutil.rmtree(_tempdir)


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

    def test_it_should_return_an_up_to_date_checker_that_fails_for_non_existent_file(self, tempdir, fs_loader):
        fp = tempdir / "foo.txt"
        is_up_to_date = fs_loader.get_up_to_date_checker(fp)
        assert is_up_to_date() is False


class TestGetSource:
    def test_it_should_return_the_file_source_and_up_to_date_checker(self, tempdir, fs_loader):
        env = Mock()
        (tempdir / "test.ravel").write_text("test!")
        with patch("os.path.getmtime") as getmtime:
            getmtime.return_value = 42.0
            result, is_up_to_date = fs_loader.get_source(env, "test")
            assert result == "test!"
            assert is_up_to_date() is True

        assert is_up_to_date() is False

    def test_it_should_raise_when_getting_source_of_nonexistent_rulebook(self, tempdir, fs_loader):
        env = Mock()
        with pytest.raises(exceptions.RulebookNotFound):
            fs_loader.get_source(env, "foo")


class TestGetSourcePathTraversal:
    def test_it_should_reject_a_relative_escape(self, tmp_path):
        base = tmp_path / "story"
        base.mkdir()
        (tmp_path / "secret.ravel").write_text("secret")
        loader = loaders.FileSystemLoader(base_path=base)
        env = Mock()

        with pytest.raises(exceptions.RulebookNotFound):
            loader.get_source(env, "../secret")

    def test_it_should_reject_an_absolute_escape(self, tmp_path):
        base = tmp_path / "story"
        base.mkdir()
        outside = tmp_path / "secret.ravel"
        outside.write_text("secret")
        loader = loaders.FileSystemLoader(base_path=base)
        env = Mock()

        with pytest.raises(exceptions.RulebookNotFound):
            loader.get_source(env, str(outside.with_suffix("")))

    def test_it_should_reject_a_symlink_escape(self, tmp_path):
        base = tmp_path / "story"
        base.mkdir()
        (tmp_path / "secret.ravel").write_text("secret")
        (base / "link").symlink_to(tmp_path)
        loader = loaders.FileSystemLoader(base_path=base)
        env = Mock()

        with pytest.raises(exceptions.RulebookNotFound):
            loader.get_source(env, "link/secret")

    def test_it_should_still_resolve_a_legitimate_subdirectory_include(self, tmp_path):
        base = tmp_path / "story"
        base.mkdir()
        sub = base / "sub"
        sub.mkdir()
        (sub / "x.ravel").write_text("ok")
        loader = loaders.FileSystemLoader(base_path=base)
        env = Mock()

        result, is_up_to_date = loader.get_source(env, "sub/x")
        assert result == "ok"


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
