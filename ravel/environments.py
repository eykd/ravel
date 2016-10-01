from collections import OrderedDict, deque, defaultdict

import attr

from ravel import loaders

from ravel.compiler import rulebooks
from ravel.compiler import yamlish

from ravel.utils.data import merge_dicts


@attr.s
class Environment:
    loader = attr.ib(attr.Factory(lambda: loaders.FileSystemLoader('.')))
    cache = attr.ib(attr.Factory(dict))

    def get_rulebook(self, name):
        loaded_rulebooks = OrderedDict()
        names_to_load = deque([name])

        while names_to_load:
            name = names_to_load.popleft()
            if name not in loaded_rulebooks:
                rulebook = rulebooks[name] = self.load_rulebook(name)
                names_to_load.extend([
                    include_name for include_name in rulebook['includes']
                    if include_name not in loaded_rulebooks
                ])

        master_rulebook = defaultdict(lambda: {'rules': [], 'locations': {}})
        for rulebook in loaded_rulebooks.values():
            for concept, ruleset in rulebook['rulebook'].items():
                master_concept = master_rulebook[concept]
                master_concept['rules'].extend(ruleset['rules'])
                master_concept['locations'].update(ruleset['locations'])

        for ruleset in master_rulebook.values():
            ruleset['rules'].sort()

        return dict(master_rulebook)

    def load_rulebook(self, name):
        rulebook = self.cache.get(name)
        if rulebook is None or not rulebook['is_up_to_date']():
            rulebook = self.loader.load(self, name)
            self.cache[name] = rulebook
        return rulebook

    def compile_rulebook(self, source, filename='', is_up_to_date=lambda: True):
        data = yamlish.parse(source, filename)

        rulebook = rulebooks.compile_rulebook(data)
        rulebook['is_up_to_date'] = is_up_to_date
        return rulebook
