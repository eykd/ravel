from ravel import parsers


def compile_text(environment, concept, parent_rule, raw_directive):
    return parsers.PlainTextParser().parse(raw_directive.text), {}
