from ravel.vm import events, states
from ravel.vm.runners import QueueRunner

from .helpers import Any


class TestStatefulRunner:
    def test_it_should_begin_playing_cloak_of_darkness(self, cloak_env):
        runner = QueueRunner(cloak_env)
        assert runner.running is False
        assert not runner._handlers
        with runner:
            assert runner.running is True
            assert runner._handlers
            assert list(runner.consume_text_events()) == []
            assert runner.choice_events == []

            result = list(runner)
            assert result == [
                events.quality_changed(quality="Location", initial_value=None, new_value="Intro"),
                events.quality_changed(quality="Wearing Cloak", initial_value=None, new_value=1),
                events.quality_changed(quality="Cloakroom", initial_value=None, new_value=0),
                events.quality_changed(quality="Fumbled", initial_value=None, new_value=0),
                events.quality_changed(quality="Bar", initial_value=None, new_value=0),
                events.quality_changed(quality="Fumbled", initial_value=0, new_value=0),
                events.quality_changed(quality="Bar", initial_value=0, new_value=0),
                events.enter_state(state=states.Begin()),
                events.pause_state(state=states.Begin()),
                events.begin_display_choices(),
                events.display_choice(
                    index=0, choice="begin::intro", text=Any(), state=states.DisplayPossibleSituations()
                ),
                events.end_display_choices(),
                events.waiting_for_input(send_input=Any(), state=states.DisplayPossibleSituations()),
                events.enter_state(state=states.DisplayPossibleSituations()),
            ]

            assert list(runner.consume_text_events()) == []
            assert runner.choice_events == [
                events.display_choice(
                    choice="begin::intro",
                    text="Hurrying through the rainswept November night…",
                    state=states.DisplayPossibleSituations(),
                    index=0,
                )
            ]
            assert runner.waiting_for_choice is True

            runner.choose(0)

            result = list(runner)
            assert result == [
                events.pause_state(state=states.DisplayPossibleSituations()),
                events.display_text(
                    text=Any(),
                    state=states.DisplaySituation(
                        situation=Any(),
                        index=5,
                        paused=False,
                    ),
                    sticky=False,
                ),
                events.begin_display_choices(),
                events.display_choice(
                    index=3,
                    choice="begin::intro::press-onward",
                    text=Any(),
                    state=states.DisplaySituation(situation=Any(), index=5, paused=False),
                ),
                events.end_display_choices(),
                events.waiting_for_input(
                    send_input=Any(), state=states.DisplaySituation(situation=Any(), index=5, paused=False)
                ),
                events.enter_state(state=states.DisplaySituation(situation=Any(), index=5, paused=False)),
                events.exit_state(state=states.DisplaySituation(situation=Any(), index=5, paused=False)),
                events.begin_display_choices(),
                events.display_choice(
                    index=0, choice="begin::intro", text=Any(), state=states.DisplayPossibleSituations()
                ),
                events.end_display_choices(),
                events.waiting_for_input(send_input=Any(), state=states.DisplayPossibleSituations()),
                events.resume_state(state=states.DisplayPossibleSituations()),
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
                    state=states.DisplaySituation(situation=Any(), index=5, paused=False),
                )
            ]
            assert runner.choice_events == [
                events.display_choice(
                    choice="begin::intro::press-onward",
                    text="Press onward!",
                    state=states.DisplaySituation(situation=Any(), index=5, paused=False),
                    index=3,
                ),
                events.display_choice(
                    choice="begin::intro",
                    text="Hurrying through the rainswept November night…",
                    state=states.DisplayPossibleSituations(),
                    index=0,
                ),
            ]
