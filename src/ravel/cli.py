"""The console front door: a thin ``ConsoleUI`` adapter over ``ravel.app.session.GameSession``.

Per ``specs/001-reentrant-vm/contracts/cli.md``. ``run`` compiles the story once via
``FileSystemStorySource``, starts or loads the game, then hands control to ``ConsoleUI.loop()``.
"""

import logging
import pdb
import sys
import textwrap
from collections.abc import Callable, Sequence

import click

from ravel.adapters.save_store import FileSaveStore
from ravel.adapters.story_source import FileSystemStorySource
from ravel.app.saves import LoadRefusedError
from ravel.app.session import DEFAULT_SAVE_NAME, GameSession
from ravel.engine.outputs import (
    ChoiceOption,
    ChoicesOffered,
    Halted,
    Output,
    QualityChanged,
    SituationEntered,
    SituationExited,
    StoryChanged,
    TextShown,
)
from ravel.engine.state import Status
from ravel.utils.strings import get_text

SEPARATOR = "-" * 80
PROMPT = "What'll it be? "

HELP_TEXT = (
    "N            choose option N from the menu",
    "save [FILE]  save the game (default: %s)" % DEFAULT_SAVE_NAME,
    "load [FILE]  load a saved game (default: %s)" % DEFAULT_SAVE_NAME,
    "s            show the current qualities",
    "help, ?      show this help",
    "q            quit",
)


class Config:
    def __init__(self) -> None:
        self.verbose = False
        self.debug = False


pass_config = click.make_pass_decorator(Config, ensure=True)


@click.group()
@click.option("--verbose", is_flag=True, default=False)
@click.option("--debug", is_flag=True, default=False)
@pass_config
def main(config: Config, verbose: bool, debug: bool) -> None:
    config.verbose = verbose
    config.debug = debug
    if verbose or debug:
        logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)


def handle_exception(exc: BaseException, *, debug: bool) -> None:
    """Log an unexpected exception, optionally drop into ``pdb``, and exit non-zero."""
    logging.exception("Something bad happened...", exc_info=exc)
    if debug:
        pdb.post_mortem()
    sys.exit(1)


def _escape_outcome(outcome: str) -> str:
    """Escape any non-printable character in ``outcome`` the way ``repr()`` would."""
    return "".join(character if character.isprintable() else repr(character)[1:-1] for character in outcome)


class ConsoleUI:
    """Renders ``Output``s to the console and drives the input prompt loop."""

    def __init__(
        self,
        session: GameSession,
        *,
        verbose: bool = False,
        read_line: Callable[[str], str] = input,
        echo: Callable[[str], None] = click.echo,
    ) -> None:
        self.session = session
        self.verbose = verbose
        self.read_line = read_line
        self.echo = echo
        self._offered: tuple[ChoiceOption, ...] = ()

    def render(self, outputs: Sequence[Output]) -> None:
        """Render ``outputs`` in order, tracking the most recently offered menu."""
        for output in outputs:
            self._render_one(output)
            if isinstance(output, ChoicesOffered):
                self._offered = output.choices

    def _render_one(self, output: Output) -> None:
        if isinstance(output, TextShown):
            self.echo(textwrap.fill(output.text))
            self.echo("")
        elif isinstance(output, ChoicesOffered):
            for index, choice in enumerate(output.choices, start=1):
                self.echo("%d: %s" % (index, choice.label))
        elif isinstance(output, QualityChanged):
            if self.verbose:
                self.echo("## %s was %r, now %r" % (output.name, output.old, output.new))
        elif isinstance(output, SituationEntered):
            if self.verbose:
                self.echo("## Entering %s" % output.location)
        elif isinstance(output, SituationExited):
            if self.verbose:
                self.echo("## Exiting %s" % output.location)
        elif isinstance(output, Halted):
            if output.dead_end:
                self.echo("*** The story has nowhere left to go. ***")
            else:
                outcome = _escape_outcome(output.outcome)
                if outcome:
                    self.echo("*** The End (outcome: %s) ***" % outcome)
                else:
                    self.echo("*** The End ***")
        else:
            # ``Output`` is a closed union and the six branches above cover every other member,
            # so this is always a ``StoryChanged`` -- an ``else`` (not another ``elif``) keeps
            # that exhaustiveness from leaving a permanently-untaken branch for coverage to flag.
            assert isinstance(output, StoryChanged)
            self.echo("The story has changed since this save; resuming at %s." % self._place_after_resume())

    def _place_after_resume(self) -> str:
        stack = self.session.state.stack
        if not stack:
            return "the top level"
        location = stack[-1].location
        return str(get_text(self.session.story.situation(location).intro))

    def _is_halted(self) -> bool:
        return self.session.state.status is Status.HALTED

    def loop(self) -> None:
        """Prompt for commands until the game halts or the player quits."""
        if self._is_halted():
            return
        while True:
            try:
                line = self.read_line(PROMPT)
            except EOFError, KeyboardInterrupt:
                self.echo("")
                return
            parts = line.strip().split(None, 1)
            word = parts[0] if parts else ""
            remainder = parts[1] if len(parts) > 1 else ""
            command = word.lower()

            if command.isdecimal():
                if self._choose(int(command)):
                    return
                continue
            if command == "save":
                self._save(remainder.strip())
                continue
            if command == "load":
                if self._load(remainder.strip()):
                    return
                continue
            if command == "s":
                self._show_qualities()
                continue
            if command in ("help", "?"):
                self._show_help()
                continue
            if command == "q":
                return
            self.echo("I'm sorry, what?")

    def _choose(self, number: int) -> bool:
        """Choose option ``number``; returns whether the game is now halted."""
        if not (1 <= number <= len(self._offered)):
            self.echo("That's not an option.")
            return False
        location = self._offered[number - 1].location
        outputs = self.session.choose(location)
        self.echo("")
        self.echo(SEPARATOR)
        self.render(outputs)
        return self._is_halted()

    def _save(self, filename: str) -> None:
        name = filename or DEFAULT_SAVE_NAME
        try:
            path = self.session.save(name)
        except OSError as error:
            self.echo("Could not save: %s" % error)
            return
        self.echo("Saved to %s." % path)

    def _load(self, filename: str) -> bool:
        """Load ``filename``; returns whether the game is now halted."""
        name = filename or DEFAULT_SAVE_NAME
        try:
            outputs = self.session.load(name)
        except LoadRefusedError as error:
            self.echo("Could not load: %s" % error)
            return False
        self.render(outputs)
        return self._is_halted()

    def _show_qualities(self) -> None:
        qualities = self.session.state.qualities.as_dict()
        for name in sorted(qualities):
            self.echo("%r = %r" % (name, qualities[name]))

    def _show_help(self) -> None:
        for line in HELP_TEXT:
            self.echo(line)


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--load", "load_file", type=click.STRING, default=None)
@pass_config
def run(config: Config, directory: str, load_file: str | None) -> None:
    """Run the story rooted at DIRECTORY."""
    try:
        story = FileSystemStorySource(directory).load()
        session = GameSession(story, FileSaveStore())
        ui = ConsoleUI(session, verbose=config.verbose)
        if load_file is not None:
            try:
                outputs = session.load(load_file)
            except LoadRefusedError as error:
                click.echo("Error: %s" % error, err=True)
                sys.exit(1)
        else:
            outputs = session.new_game()
        ui.render(outputs)
        ui.loop()
    except Exception as error:
        handle_exception(error, debug=config.debug)
