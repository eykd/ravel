from . import compilers


def load_rules(rule_defs):
    return compile_rulebook({
        ('%s: %s' % (name, key)): value
        for name, ruleset in rule_defs
        for key, value in ruleset.items()
    })
