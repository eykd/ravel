from unittest import TestCase
from ensure import ensure

from ravel.compiler import concepts


class TestGetHandlerFor(TestCase):
    def test_it_should_get_a_dummy_handler_for_undefined_handlers(self):
        ensure('foo').is_not_in(concepts._HANDLERS)
        (ensure(concepts.get_handler_for)
         .called_with('foo')
         .is_(concepts._dummy_handler))


class TestHandlerDecorator(TestCase):
    def test_it_should_register_a_handler_by_concept(self):
        def my_handler(x):
            return x * 2

        result = concepts.handler('bar')(my_handler)
        ensure(result).is_(my_handler)
        (ensure(concepts._HANDLERS)
         .has_key('bar')  # noqa
         .whose_value.is_(my_handler)
        )


class Test_DummyHandler(TestCase):
    def test_it_should_perform_no_op_on_baggage(self):
        rule_name = 'foo'
        value = ['bar']
        (ensure(concepts._dummy_handler)
         .called_with('concept', rule_name, value).equals({rule_name: value}))
