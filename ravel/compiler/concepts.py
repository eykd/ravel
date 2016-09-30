from ravel.utils.strings import get_text


_HANDLERS = {}


def handler(concept):
    """Decorator for concept handlers.

    Usage:

        @baggage.handler('MyConcept')
        def handle_myconcept(concept, rule_name, baggage):
            return "something else based on the baggage!"
    """
    def register_handler(func):
        _HANDLERS[concept] = func
        return func

    return register_handler


def _dummy_handler(concept, rule_name, baggage):
    """Return the baggage as-is.
    """
    return {rule_name: [get_text(b) for b in baggage]}


def get_handler_for(concept):
    """Return a handler for the given concept.
    """
    return _HANDLERS.get(concept, _dummy_handler)


def compile_baggage(concept, rule_name, baggage_data):
    """Compile the given baggage using a registered concept handler.
    """
    return get_handler_for(concept)(concept, rule_name, baggage_data)
