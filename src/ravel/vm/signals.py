from blinker import signal


class Signals:
    begin = signal("begin")
    end = signal("end")

    enter_state = signal("enter_state")
    exit_state = signal("exit_state")
    pause_state = signal("pause_state")
    resume_state = signal("resume_state")

    display_text = signal("display_text")

    begin_display_choices = signal("begin_display_choices")
    display_choice = signal("display_choice")
    end_display_choices = signal("end_display_choices")

    waiting_for_input = signal("waiting_for_input")

    end_display_situation = signal("end_display_situation")

    quality_changed = signal("quality_changed")
