def merge_dicts(*dicts):
    """
    Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


def evaluate_term(term, **kwargs):
    return term.evaluate(**kwargs) if hasattr(term, "evaluate") else term
