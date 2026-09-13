import logging
import pdb
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from ravel import cli
from ravel.vm import events, states


@pytest.fixture
def cloak_path(examples_path):
    return str(examples_path / "cloak")


def scripted_input(*responses):
    """Build a get_input replacement that answers with each response in turn.

    The sequence must end in a quit, or the console runner's ``while True``
    loop restarts the story forever. Exhausting it raises EOFError, which
    ``run`` treats as a clean exit, rather than StopIteration, which its bare
    ``except Exception`` would route into ``handle_exception``.
    """
    remaining = iter(responses)

    def get_input(text):
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    return get_input


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
        monkeypatch.setattr(cli.ConsoleRunner, "get_input", staticmethod(scripted_input("q")))

        result = CliRunner().invoke(cli.main, [*flags, "run", cloak_path])

        assert result.exit_code == 0
        basic_config.assert_called_once_with(level=expected)


class TestRunCommand:
    def test_it_should_play_the_story_until_the_player_quits(self, cloak_path, monkeypatch):
        monkeypatch.setattr(cli.ConsoleRunner, "get_input", staticmethod(scripted_input("1", "1", "q")))
        result = CliRunner().invoke(cli.main, ["run", cloak_path])
        assert result.exit_code == 0
        assert "rainswept November night" in result.output

    def test_it_should_report_a_broken_story(self, tmp_path, monkeypatch):
        (tmp_path / "begin.ravel").write_text("when:\n  - not a comparison\n\nintro:\n\n  - Hi.\n")
        result = CliRunner().invoke(cli.main, ["run", str(tmp_path)])
        assert result.exit_code != 0
        assert "Line 2" in str(result.exception)


class TestConsoleRunner:
    def build(self, cloak_env, responses, **kwargs):
        runner = cli.ConsoleRunner(cloak_env, **kwargs)
        runner.get_input = scripted_input(*responses)
        return runner

    def test_it_should_exit_cleanly_on_quit(self, cloak_env, capsys):
        runner = self.build(cloak_env, ["q"])
        with runner, pytest.raises(SystemExit) as excinfo:
            runner.run()
        assert excinfo.value.code == 0

    def test_it_should_exit_cleanly_when_input_runs_out(self, cloak_env):
        runner = self.build(cloak_env, [])
        with runner, pytest.raises(SystemExit) as excinfo:
            runner.run()
        assert excinfo.value.code == 0

    def test_it_should_reject_an_out_of_range_choice(self, cloak_env, capsys):
        runner = self.build(cloak_env, ["9", "q"])
        with runner, pytest.raises(SystemExit):
            runner.run()
        assert "not an option" in capsys.readouterr().out

    def test_it_should_reject_an_unrecognized_answer(self, cloak_env, capsys):
        runner = self.build(cloak_env, ["wat", "q"])
        with runner, pytest.raises(SystemExit):
            runner.run()
        assert "I'm sorry, what?" in capsys.readouterr().out

    def test_it_should_dump_qualities_on_s(self, cloak_env, capsys):
        runner = self.build(cloak_env, ["s", "q"])
        with runner, pytest.raises(SystemExit):
            runner.run()
        assert "Wearing Cloak" in capsys.readouterr().out

    def test_it_should_display_text(self, cloak_env, capsys):
        runner = self.build(cloak_env, ["1", "1", "q"])
        with runner, pytest.raises(SystemExit):
            runner.run()
        assert "rainswept November night" in capsys.readouterr().out


class TestConsoleRunnerVerbosity:
    EVENTS = [
        ("handle_quality_changed", events.quality_changed(quality="Bar", initial_value=0, new_value=1), "Bar"),
        ("handle_enter_state", events.enter_state(state=states.Begin()), "Entering"),
        ("handle_exit_state", events.exit_state(state=states.Begin()), "Exiting"),
        ("handle_pause_state", events.pause_state(state=states.Begin()), "Pausing"),
        ("handle_resume_state", events.resume_state(state=states.Begin()), "Resuming"),
    ]

    @pytest.mark.parametrize("handler_name, event, expected", EVENTS)
    def test_it_should_narrate_when_verbose(self, cloak_env, capsys, handler_name, event, expected):
        runner = cli.ConsoleRunner(cloak_env, verbose=True)
        getattr(runner, handler_name)(event)
        assert expected in capsys.readouterr().out

    @pytest.mark.parametrize("handler_name, event, expected", EVENTS)
    def test_it_should_stay_quiet_otherwise(self, cloak_env, capsys, handler_name, event, expected):
        runner = cli.ConsoleRunner(cloak_env, verbose=False)
        getattr(runner, handler_name)(event)
        assert capsys.readouterr().out == ""


class TestHandleException:
    def test_it_should_exit_nonzero(self, cloak_env):
        runner = cli.ConsoleRunner(cloak_env)
        with pytest.raises(SystemExit) as excinfo:
            runner.handle_exception(ValueError("boom"))
        assert excinfo.value.code == 1

    def test_it_should_drop_into_the_debugger_only_with_debug(self, cloak_env, monkeypatch):
        post_mortem = Mock()
        monkeypatch.setattr(pdb, "post_mortem", post_mortem)

        runner = cli.ConsoleRunner(cloak_env, debug=False)
        with pytest.raises(SystemExit):
            runner.handle_exception(ValueError("boom"))
        post_mortem.assert_not_called()

        runner = cli.ConsoleRunner(cloak_env, debug=True)
        with pytest.raises(SystemExit):
            runner.handle_exception(ValueError("boom"))
        post_mortem.assert_called_once_with()

    def test_it_should_route_story_failures_through_handle_exception(self):
        runner = cli.ConsoleRunner.__new__(cli.ConsoleRunner)
        runner.debug = False
        runner.vm = Mock(run=Mock(side_effect=RuntimeError("nope")))
        with pytest.raises(SystemExit) as excinfo:
            runner.run()
        assert excinfo.value.code == 1


class TestGetInput:
    def test_it_should_read_from_stdin(self, cloak_env, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "typed")
        runner = cli.ConsoleRunner(cloak_env)
        assert runner.get_input("{green}?{/green} ") == "typed"
