from enum import Enum

from blinker import signal


class SIGNAL(Enum):
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
    begin = signal(SIGNAL.begin.value)
    end = signal(SIGNAL.end.value)

    enter_state = signal(SIGNAL.enter_state.value)
    exit_state = signal(SIGNAL.exit_state.value)
    pause_state = signal(SIGNAL.pause_state.value)
    resume_state = signal(SIGNAL.resume_state.value)

    display_text = signal(SIGNAL.display_text.value)

    begin_display_choices = signal(SIGNAL.begin_display_choices.value)
    display_choice = signal(SIGNAL.display_choice.value)
    end_display_choices = signal(SIGNAL.end_display_choices.value)

    waiting_for_input = signal(SIGNAL.waiting_for_input.value)

    quality_changed = signal(SIGNAL.quality_changed.value)
