from collections import OrderedDict, deque, defaultdict

import attr
import syml

from ravel import loaders

from ravel.compiler import rulebooks


@attr.s
class Environment:
    loader = attr.ib(default=attr.Factory(lambda: loaders.FileSystemLoader()))
    location_separator = attr.ib(default='::')
    initializing_name = attr.ib(default='begin')

    cache = attr.ib(default=attr.Factory(dict))

    def load(self):
        return self.load_rulebook(self.initializing_name)

    def load_rulebook(self, name):
        loaded_rulebooks = OrderedDict()
        names_to_load = deque([name])
        metadata = {}
        givens = []

        while names_to_load:
            name = names_to_load.popleft()
            if name not in loaded_rulebooks:
                rulebook = loaded_rulebooks[name] = self.get_rulebook(name)
                names_to_load.extend([
                    include_name for include_name in rulebook['includes']
                    if include_name not in loaded_rulebooks
                ])
                metadata.update(rulebook['metadata'])
                givens.extend(rulebook['givens'])

        master_rulebook = defaultdict(lambda: {'rules': [], 'locations': {}})
        for rulebook in loaded_rulebooks.values():
            for concept, ruleset in rulebook['rulebook'].items():
                master_concept = master_rulebook[concept]
                master_concept['rules'].extend(ruleset['rules'])
                master_concept['locations'].update(ruleset['locations'])

        for ruleset in master_rulebook.values():
            ruleset['rules'].sort()

        return {
            'metadata': metadata,
            'rulebook': dict(master_rulebook),
            'givens': givens,
        }

    def get_rulebook(self, name):
        rulebook = self.cache.get(name)
        if rulebook is None or not rulebook['is_up_to_date']():
            rulebook = self.loader.load(self, name)
            self.cache[name] = rulebook
        return rulebook

    @staticmethod
    def default_is_up_to_date():
        return True

    def compile_rulebook(self, source, name='', is_up_to_date=default_is_up_to_date):
        data = syml.loads(source, filename=name)

        prefix = name + self.location_separator if name else ''
        rulebook = rulebooks.compile_rulebook(self, data, prefix)
        rulebook['is_up_to_date'] = is_up_to_date
        return rulebook
