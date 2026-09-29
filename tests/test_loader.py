import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ravel import exceptions, loaders
from ravel.environments import MAX_RULEBOOK_BYTES, Environment
from ravel.types import Rule


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


class TestMemoryLoader:
    def test_it_should_serve_rulebooks_from_the_mapping(self):
        env = Environment(loader=loaders.MemoryLoader({"begin": "intro:\n  - Hi[.] there.\n"}))
        assert env.load()["rulebook"]["Situation"]["rules"] == [Rule("begin::intro", [])]

    def test_it_should_raise_when_the_rulebook_is_missing(self):
        env = Environment(loader=loaders.MemoryLoader({}))
        with pytest.raises(exceptions.RulebookNotFound, match="begin"):
            env.load()

    def test_get_source_should_return_source_and_an_always_true_checker(self):
        loader = loaders.MemoryLoader({"begin": "text"})
        source, is_up_to_date = loader.get_source(Mock(), "begin")
        assert source == "text"
        assert is_up_to_date() is True

    def test_it_should_copy_the_mapping_at_construction(self):
        sources = {"begin": "intro:\n  - Hi[.] there.\n"}
        loader = loaders.MemoryLoader(sources)
        sources["begin"] = "other:\n  - Bye[.] now.\n"
        assert loader.get_source(Mock(), "begin")[0] == "intro:\n  - Hi[.] there.\n"

    def test_it_should_follow_includes_between_in_memory_rulebooks(self):
        env = Environment(
            loader=loaders.MemoryLoader(
                {
                    "begin": "include:\n  - other\n\nintro:\n  - Hi[.] there.\n",
                    "other": "outro:\n  - Bye[.] now.\n",
                }
            )
        )
        names = {rule.name for rule in env.load()["rulebook"]["Situation"]["rules"]}
        assert names == {"begin::intro", "other::outro"}


class TestRulebookSourceLimits:
    def test_fs_loader_rejects_oversize_file_reading_only_cap_plus_one(self, tempdir, fs_loader):
        (tempdir / "big.ravel").write_bytes(b"a" * (MAX_RULEBOOK_BYTES + 5))
        real_open = Path.open
        reads = []

        class Spy:
            def __init__(self, fh):
                self._fh = fh

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self._fh.close()

            def read(self, n=-1):
                reads.append(n)
                return self._fh.read(n)

        def spy_open(self, *args, **kwargs):
            return Spy(real_open(self, *args, **kwargs))

        with patch.object(Path, "open", spy_open), pytest.raises(exceptions.RulebookTooLargeError, match="big"):
            fs_loader.get_source(None, "big")
        assert reads == [MAX_RULEBOOK_BYTES + 1]

    def test_fs_loader_accepts_file_at_cap(self, tempdir, fs_loader):
        (tempdir / "ok.ravel").write_bytes(b"a" * MAX_RULEBOOK_BYTES)
        source, _ = fs_loader.get_source(None, "ok")
        assert len(source) == MAX_RULEBOOK_BYTES

    def test_fs_loader_maps_bad_utf8_to_parse_error(self, tempdir, fs_loader):
        (tempdir / "bad.ravel").write_bytes(b"\xff\xfe\x00")
        with pytest.raises(exceptions.ParseError, match="bad") as info:
            fs_loader.get_source(None, "bad")
        assert str(tempdir) not in str(info.value)

    def test_fs_loader_maps_directory_to_not_found(self, tempdir, fs_loader):
        (tempdir / "x.ravel").mkdir()
        with pytest.raises(exceptions.RulebookNotFound):
            fs_loader.get_source(None, "x")

    def test_fs_loader_maps_nul_name_to_not_found(self, fs_loader):
        with pytest.raises(exceptions.RulebookNotFound):
            fs_loader.get_source(None, "a\0b")

    def test_fs_loader_maps_read_oserror_to_not_found(self, tempdir, fs_loader):
        (tempdir / "z.ravel").write_text("x")
        with (
            patch.object(Path, "open", side_effect=PermissionError("nope")),
            pytest.raises(exceptions.RulebookNotFound),
        ):
            fs_loader.get_source(None, "z")

    def test_fs_loader_still_blocks_traversal(self, fs_loader):
        with pytest.raises(exceptions.RulebookNotFound, match="escapes"):
            fs_loader.get_source(None, "../evil")

    def test_custom_loader_oversize_source_is_refused_at_load(self):
        class BigLoader(loaders.BaseLoader):
            def get_source(self, environment, name):
                return "a" * (2 * 1024 * 1024), lambda: True

        with pytest.raises(exceptions.RulebookTooLargeError, match="begin"):
            Environment(loader=BigLoader()).load()

    def test_compile_rulebook_counts_bytes_not_characters(self):
        with pytest.raises(exceptions.RulebookTooLargeError):
            Environment(loader=loaders.MemoryLoader({})).compile_rulebook("é" * (MAX_RULEBOOK_BYTES // 2 + 1), "wide")

    def test_memory_loader_oversize_source_is_refused_at_load(self):
        env = Environment(loader=loaders.MemoryLoader({"begin": "a" * (MAX_RULEBOOK_BYTES + 1)}))
        with pytest.raises(exceptions.RulebookTooLargeError, match="begin"):
            env.load()

    def test_compile_rulebook_accepts_source_at_cap(self):
        env = Environment(loader=loaders.MemoryLoader({}))
        source = "intro:\n  - Bye[.] now.\n"
        env.compile_rulebook(source + "#" * (MAX_RULEBOOK_BYTES - len(source)), "ok")

    def test_memory_loader_counts_lone_surrogates(self):
        loader = loaders.MemoryLoader({"s": "\ud800"})
        source, _ = loader.get_source(None, "s")
        assert source == "\ud800"

    @pytest.mark.parametrize("kind", ["big", "bad_utf8", "directory", "nul"])
    def test_environment_load_raises_typed_errors(self, tempdir, kind):
        if kind == "big":
            (tempdir / "begin.ravel").write_bytes(b"a" * (MAX_RULEBOOK_BYTES + 1))
            expected = exceptions.RulebookTooLargeError
        elif kind == "bad_utf8":
            (tempdir / "begin.ravel").write_bytes(b"\xff\xfe")
            expected = exceptions.ParseError
        elif kind == "directory":
            (tempdir / "begin.ravel").mkdir()
            expected = exceptions.RulebookNotFound
        else:
            (tempdir / "begin.ravel").write_text("x")
            expected = exceptions.RulebookNotFound
        env = Environment(loader=loaders.FileSystemLoader(base_path=tempdir))
        if kind == "nul":
            with pytest.raises(expected):
                env.load_rulebook("a\0b")
        else:
            with pytest.raises(expected):
                env.load()


class TestBoundedNames:
    def test_it_should_escape_control_characters_in_a_missing_include_name(self, fs_loader):
        with pytest.raises(exceptions.RulebookNotFound) as info:
            fs_loader.get_source(Mock(), "no\x1b[31m\nsuch")

        assert str(info.value) == "no\\x1b[31m\\nsuch"

    def test_it_should_bound_an_oversized_missing_name(self, fs_loader):
        with pytest.raises(exceptions.RulebookNotFound) as info:
            fs_loader.get_source(Mock(), "n" * 5000)

        assert len(str(info.value)) < 512

    def test_it_should_escape_the_name_in_the_invalid_and_escaping_messages(self, fs_loader):
        with pytest.raises(exceptions.RulebookNotFound) as info:
            fs_loader.get_source(Mock(), "a\0\x1b")
        assert "\x1b" not in str(info.value)

        with pytest.raises(exceptions.RulebookNotFound) as info:
            fs_loader.get_source(Mock(), "../\x1b" + "x" * 5000)
        assert "\x1b" not in str(info.value)
        assert len(str(info.value)) < 512
