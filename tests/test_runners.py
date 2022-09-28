import pytest

from ravel.environments import Environment
from ravel.loaders import FileSystemLoader
from ravel.vm import events
from ravel.vm.runners import StatefulRunner

from .helpers import Any


@pytest.fixture
def cloak_env(examples_path):
    return Environment(
        loader=FileSystemLoader(base_path=examples_path / "cloak"),
    )


class TestStatefulRunner:
    def test_it_should_begin_playing_cloak_of_darkness(self, cloak_env):
        runner = StatefulRunner(cloak_env)
        assert runner.running is False
        assert not runner._handlers
        with runner:
            assert runner.running is True
            assert runner._handlers
            assert list(runner.consume_text_events()) == []
            assert runner.choice_events == []

            result = list(runner)
            assert result == [
                events.quality_changed(quality="Intro", initial_value=None, new_value=1),
                events.quality_changed(quality="Wearing Cloak", initial_value=None, new_value=1),
                events.quality_changed(quality="Fumbled", initial_value=None, new_value=0),
                events.quality_changed(quality="Fumbled", initial_value=0, new_value=0),
                events.enter_state(state=Any()),
                events.pause_state(state=Any()),
                events.begin_display_choices(),
                events.display_choice(index=0, choice="begin::intro", text=Any(), state=Any()),
                events.end_display_choices(),
                events.waiting_for_input(send_input=Any(), state=Any()),
                events.enter_state(state=Any()),
            ]

            assert list(runner.consume_text_events()) == []
            assert runner.choice_events == [
                events.display_choice(
                    choice="begin::intro",
                    text="Hurrying through the rainswept November night…",
                    state=Any(),
                    index=0,
                )
            ]
            assert runner.waiting_for_choice is True

            runner.choose(0)

            result = list(runner)
            assert result == [
                events.pause_state(state=Any()),
                events.display_text(text=Any(), state=Any(), sticky=False),
                events.begin_display_choices(),
                events.display_choice(index=3, choice="begin::intro::press-onward", text=Any(), state=Any()),
                events.end_display_choices(),
                events.waiting_for_input(send_input=Any(), state=Any()),
                events.enter_state(state=Any()),
                events.exit_state(state=Any()),
                events.begin_display_choices(),
                events.display_choice(index=0, choice="begin::intro", text=Any(), state=Any()),
                events.end_display_choices(),
                events.waiting_for_input(send_input=Any(), state=Any()),
                events.resume_state(state=Any()),
            ]

            assert list(runner.consume_text_events()) == [
                events.display_text(
                    text=(
                        "Hurrying through the rainswept November night, you're "
                        "glad to see the bright lights of the Opera House. It's "
                        "surprising that there aren't more people about but, hey, "
                        "what do you expect in a cheap demo game…?"
                    ),
                    sticky=False,
                    state=Any(),
                )
            ]
            assert runner.choice_events == [
                events.display_choice(choice="begin::intro::press-onward", text="Press onward!", state=Any(), index=3),
                events.display_choice(
                    choice="begin::intro", text="Hurrying through the rainswept November night…", state=Any(), index=0
                ),
            ]
