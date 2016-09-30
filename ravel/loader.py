from . import compilers


def load_rules(config, story):
    """Run the indicated storyfile.
    """
    state = {}
    try:
        rulebook = rules.compile_rulebook(yamlish.parse(story.read()).as_data())
    except:
        logging.exception('Something bad happened while compiling the rulebook...')
        import ipdb
        ipdb.post_mortem()
        sys.exit(1)



def load_rules(rule_defs):
    return compile_rulebook({
        ('%s: %s' % (name, key)): value
        for name, ruleset in rule_defs
        for key, value in ruleset.items()
    })
