"""Unit tests for ``ravel.adapters.save_store.FileSaveStore`` (contracts/session-api.md)."""

import os
import stat

import pytest

from ravel.adapters.save_store import FileSaveStore
from ravel.app.saves import MAX_SAVE_BYTES, SAVE_MAGIC


def test_write_creates_the_file_with_the_given_bytes(tmp_path):
    store = FileSaveStore(tmp_path)

    display_path = store.write("save.json", SAVE_MAGIC + b'","x":1}')

    assert display_path == str(tmp_path / "save.json")
    assert (tmp_path / "save.json").read_bytes() == SAVE_MAGIC + b'","x":1}'


def test_write_removes_the_temp_file_if_the_replace_fails(tmp_path, monkeypatch):
    store = FileSaveStore(tmp_path)

    def raising_replace(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(os, "replace", raising_replace)

    with pytest.raises(OSError, match="boom"):
        store.write("save.json", b"data")

    assert list(tmp_path.iterdir()) == []


def test_write_sets_mode_from_umask_not_mkstemps_default(tmp_path):
    store = FileSaveStore(tmp_path)
    old_umask = os.umask(0o022)
    try:
        store.write("save.json", b"data")
    finally:
        os.umask(old_umask)

    mode = stat.S_IMODE((tmp_path / "save.json").stat().st_mode)
    assert mode == 0o666 & ~0o022


def test_write_overwrites_an_empty_existing_file(tmp_path):
    store = FileSaveStore(tmp_path)
    (tmp_path / "save.json").write_bytes(b"")

    store.write("save.json", SAVE_MAGIC + b'"}')

    assert (tmp_path / "save.json").read_bytes() == SAVE_MAGIC + b'"}'


def test_write_overwrites_an_existing_ravel_save(tmp_path):
    store = FileSaveStore(tmp_path)
    (tmp_path / "save.json").write_bytes(SAVE_MAGIC + b'","old":true}')

    store.write("save.json", SAVE_MAGIC + b'","new":true}')

    assert (tmp_path / "save.json").read_bytes() == SAVE_MAGIC + b'","new":true}'


def test_write_refuses_to_clobber_a_foreign_non_empty_file(tmp_path):
    store = FileSaveStore(tmp_path)
    foreign = tmp_path / "story.ravel"
    foreign.write_bytes(b"begin:\n  - situation: intro\n")

    with pytest.raises(FileExistsError, match="story.ravel"):
        store.write("story.ravel", SAVE_MAGIC + b'"}')

    assert foreign.read_bytes() == b"begin:\n  - situation: intro\n"


def test_read_refuses_a_directory(tmp_path):
    store = FileSaveStore(tmp_path)
    (tmp_path / "adir").mkdir()

    with pytest.raises(OSError, match="not a regular file"):
        store.read("adir")


def test_read_refuses_a_fifo_without_hanging(tmp_path):
    store = FileSaveStore(tmp_path)
    fifo_path = tmp_path / "afifo"
    os.mkfifo(fifo_path)

    with pytest.raises(OSError, match="not a regular file"):
        store.read("afifo")


def test_read_reads_at_most_max_save_bytes_plus_one(tmp_path):
    store = FileSaveStore(tmp_path)
    oversize = tmp_path / "big.json"
    with open(oversize, "wb") as big_file:
        big_file.truncate(MAX_SAVE_BYTES + 100)

    data = store.read("big.json")

    assert len(data) == MAX_SAVE_BYTES + 1


def test_base_none_resolves_against_cwd_at_call_time(tmp_path, monkeypatch):
    store = FileSaveStore(base=None)
    monkeypatch.chdir(tmp_path)

    store.write("save.json", SAVE_MAGIC + b'"}')

    assert (tmp_path / "save.json").read_bytes() == SAVE_MAGIC + b'"}'

    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)

    with pytest.raises(FileNotFoundError):
        store.read("save.json")
