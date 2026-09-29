from ravel import environments, loaders
from ravel.compiler import concepts


class TestGetHandlerFor:
    def test_it_should_get_a_dummy_handler_for_undefined_handlers(self):
        assert "foo" not in concepts._HANDLERS

        assert concepts.get_handler_for("foo") is concepts._dummy_handler


class TestHandlerDecorator:
    def test_it_should_register_a_handler_by_concept(self):
        def my_handler(x):
            return x * 2

        result = concepts.handler("bar")(my_handler)
        assert result is my_handler

        assert "bar" in concepts._HANDLERS
        assert concepts._HANDLERS["bar"] is my_handler


class Test_DummyHandler:
    def test_it_should_perform_no_op_on_baggage(self):
        rule_name = "foo"
        value = ["bar"]

        result = concepts._dummy_handler(
            environments.Environment(loader=loaders.MemoryLoader({})), "concept", rule_name, value
        )
        expected = {rule_name: value}
        assert result == expected


class TestIsRegistered:
    def test_it_should_report_a_registered_concept(self):
        assert concepts.is_registered("Situation") is True

    def test_it_should_not_report_an_unregistered_concept(self):
        assert concepts.is_registered("Hello") is False

    def test_it_should_match_concept_names_exactly(self):
        assert concepts.is_registered("situation") is False
