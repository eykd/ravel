import pytest

from ravel.environments import Environment
from ravel.loaders import FileSystemLoader
from ravel.vm.runners import DisplayChoice, DisplayText, StatefulRunner


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
            assert runner.out_queue == []
            assert runner.choices == []

            for _ in runner:
                pass

            assert runner.out_queue == []
            assert runner.choices == [
                DisplayChoice(
                    choice="begin::intro",
                    text="Hurrying through the rainswept November night…",
                )
            ]
            assert runner.waiting_for_choice is True

            runner.choose(0)

            for _ in runner:
                pass

            assert runner.out_queue == [
                DisplayText(
                    text=(
                        "Hurrying through the rainswept November night, you're "
                        "glad to see the bright lights of the Opera House. It's "
                        "surprising that there aren't more people about but, hey, "
                        "what do you expect in a cheap demo game…?"
                    ),
                    sticky=False,
                )
            ]
            assert runner.choices == [
                DisplayChoice(choice="begin::intro::press-onward", text="Press onward!"),
                DisplayChoice(choice="begin::intro", text="Hurrying through the rainswept November night…"),
            ]
