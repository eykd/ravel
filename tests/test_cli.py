import logging
import pdb
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from ravel import cli, types
from ravel.app.saves import SaveTooLargeError
from ravel.engine.engine import choose
from ravel.engine.outputs import (
    ChoiceOption,
    ChoicesOffered,
    Halted,
    QualityChanged,
    SituationEntered,
    SituationExited,
    StoryChanged,
    TextShown,
)
from ravel.engine.state import GameState, Qualities, Status
from ravel.engine.story import Story


@pytest.fixture
def cloak_path(examples_path):
    return str(examples_path / "cloak")


class TestMain:
    """The group callback only runs when a subcommand does, so these drive `run`."""

    @pytest.mark.parametrize(
        "flags, expected",
        [
            ([], logging.WARNING),
            (["--verbose"], logging.INFO),
            (["--debug"], logging.DEBUG),
        ],
    )
    def test_it_should_set_the_log_level(self, cloak_path, monkeypatch, flags, expected):
        basic_config = Mock()
        monkeypatch.setattr(logging, "basicConfig", basic_config)

        result = CliRunner().invoke(cli.main, [*flags, "run", cloak_path], input="q\n")

        assert result.exit_code == 0
        basic_config.assert_called_once_with(level=expected)


class TestHandleException:
    def test_it_should_exit_nonzero(self):
        with pytest.raises(SystemExit) as excinfo:
            cli.handle_exception(ValueError("boom"), debug=False)
        assert excinfo.value.code == 1

    def test_it_should_drop_into_the_debugger_only_with_debug(self, monkeypatch):
        post_mortem = Mock()
        monkeypatch.setattr(pdb, "post_mortem", post_mortem)

        with pytest.raises(SystemExit):
            cli.handle_exception(ValueError("boom"), debug=False)
        post_mortem.assert_not_called()

        with pytest.raises(SystemExit):
            cli.handle_exception(ValueError("boom"), debug=True)
        post_mortem.assert_called_once_with()


class _StubSession:
    """A minimal stand-in for ``GameSession`` for the ``ConsoleUI`` branches the acceptance test
    can't reach through a real story: an empty-outcome halt, ``StoryChanged`` at both stack
    depths, an already-halted startup, and a ``load`` that immediately halts."""

    def __init__(self, *, status=Status.WAITING, stack=(), qualities=None, load_outputs=(), save_error=None):
        self.state = SimpleNamespace(
            status=status, stack=stack, qualities=SimpleNamespace(as_dict=lambda: qualities or {})
        )
        self.story = SimpleNamespace(situation=lambda location: SimpleNamespace(intro="intro:%s" % location))
        self._load_outputs = load_outputs
        self._save_error = save_error

    def save(self, name):
        raise self._save_error

    def load(self, name):
        self.state = SimpleNamespace(status=Status.HALTED, stack=(), qualities=self.state.qualities)
        return self._load_outputs


class TestConsoleUI:
    def test_render_halted_with_empty_outcome(self):
        lines = []
        ui = cli.ConsoleUI(_StubSession(), echo=lines.append)

        ui.render((Halted("", False),))

        assert lines == ["*** The End ***"]

    def test_render_halted_escapes_control_characters_in_the_outcome(self):
        lines = []
        ui = cli.ConsoleUI(_StubSession(), echo=lines.append)

        ui.render((Halted("\x1bwon", False),))

        assert lines == ["*** The End (outcome: \\x1bwon) ***"]

    def test_render_escapes_ansi_and_bel_in_story_text_but_collapses_only_by_the_existing_wrap(self):
        lines = []
        ui = cli.ConsoleUI(_StubSession(), echo=lines.append)

        ui.render((TextShown("\x1b]0;pwned\x07hello next\x7f\x85 caf\u00e9"),))

        assert lines == ["\\x1b]0;pwned\\x07hello next\\x7f\\x85 caf\u00e9", ""]
        assert not any("\x1b" in line or "\x07" in line for line in lines)

    def test_render_escapes_control_characters_in_labels_and_verbose_lines(self):
        lines = []
        ui = cli.ConsoleUI(_StubSession(), verbose=True, echo=lines.append)
        choices = (ChoiceOption(location="s", label="Go\x1b[2J\nTab\there"),)

        ui.render(
            (
                ChoicesOffered(choices),
                QualityChanged("q\x07", 0, "a\x1b"),
                SituationEntered("in\x1b"),
                SituationExited("out\x07"),
            )
        )

        assert lines == [
            "1: Go\\x1b[2J\nTab\there",
            "## q\\x07 was 0, now 'a\\x1b'",
            "## Entering in\\x1b",
            "## Exiting out\\x07",
        ]

    def test_engine_text_shown_still_carries_the_raw_text(self):
        raw = "\x1b]0;pwned\x07hello"
        rulebook: types.CompiledRulebook = {
            "metadata": {},
            "rulebook": {
                "Situation": {
                    "rules": [types.Rule("s", [])],
                    "locations": {"s": types.Situation(intro=types.Text("S"), directives=[types.Text(raw)])},
                }
            },
            "givens": [],
        }

        state = GameState(qualities=Qualities(), stack=(), status=Status.WAITING, offered=("s",), outcome=None)

        step = choose(Story(rulebook=rulebook), state, "s")

        assert TextShown(raw) in step.outputs

    def test_render_story_changed_with_a_non_empty_stack(self):
        lines = []
        stack = (SimpleNamespace(location="begin::fork"),)
        ui = cli.ConsoleUI(_StubSession(stack=stack), echo=lines.append)

        ui.render((StoryChanged(dropped=("begin::bridge",)),))

        assert lines == ["The story has changed since this save; resuming at intro:begin::fork."]

    def test_render_story_changed_with_an_empty_stack(self):
        lines = []
        ui = cli.ConsoleUI(_StubSession(stack=()), echo=lines.append)

        ui.render((StoryChanged(dropped=("begin::fork",)),))

        assert lines == ["The story has changed since this save; resuming at the top level."]

    def test_loop_returns_immediately_when_already_halted(self):
        read_line = Mock()
        ui = cli.ConsoleUI(_StubSession(status=Status.HALTED), read_line=read_line, echo=Mock())

        ui.loop()

        read_line.assert_not_called()

    def test_save_command_reports_an_oversize_save_and_keeps_the_prompt_loop_running(self):
        lines = []
        answers = iter(["save big.json", "q"])
        session = _StubSession(save_error=SaveTooLargeError("save is too large to write (over 1 MiB)"))
        ui = cli.ConsoleUI(session, read_line=lambda prompt: next(answers), echo=lines.append)

        ui.loop()

        assert "Could not save: save is too large to write (over 1 MiB)" in lines
        assert not any(line.startswith("Saved to") for line in lines)

    def test_load_command_that_halts_ends_the_loop_without_reprompting(self):
        lines = []
        halted_outputs = (Halted("won", False),)
        session = _StubSession(load_outputs=halted_outputs)
        offered = (ChoiceOption(location="begin::fork", label="Fork"),)
        ui = cli.ConsoleUI(session, read_line=lambda prompt: "load save.json", echo=lines.append)
        ui.render((ChoicesOffered(offered),))
        lines.clear()

        ui.loop()

        assert lines[-1] == "*** The End (outcome: won) ***"
