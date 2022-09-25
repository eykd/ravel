from ravel import parsers
from ravel.utils.strings import get_text


def compile_text(environment, concept, parent_rule, raw_directive):
    text = get_text(raw_directive).replace("\n", " ")
    return parsers.PlainTextParser().parse(text), {}
