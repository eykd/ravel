from enum import Enum

from blinker import signal


class SIGNALS(Enum):
    begin = "begin"
    end = "end"

    enter_state = "enter_state"
    exit_state = "exit_state"
    pause_state = "pause_state"
    resume_state = "resume_state"

    display_text = "display_text"

    begin_display_choices = "begin_display_choices"
    display_choice = "display_choice"
    end_display_choices = "end_display_choices"

    waiting_for_input = "waiting_for_input"

    quality_changed = "quality_changed"


class Signals:
    begin = signal(SIGNALS.begin.value)
    end = signal(SIGNALS.end.value)

    enter_state = signal(SIGNALS.enter_state.value)
    exit_state = signal(SIGNALS.exit_state.value)
    pause_state = signal(SIGNALS.pause_state.value)
    resume_state = signal(SIGNALS.resume_state.value)

    display_text = signal(SIGNALS.display_text.value)

    begin_display_choices = signal(SIGNALS.begin_display_choices.value)
    display_choice = signal(SIGNALS.display_choice.value)
    end_display_choices = signal(SIGNALS.end_display_choices.value)

    waiting_for_input = signal(SIGNALS.waiting_for_input.value)

    quality_changed = signal(SIGNALS.quality_changed.value)
