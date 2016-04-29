from collections import namedtuple

Comparison = namedtuple('Comparison', ['quality', 'comparison', 'expression'])
Constraint = namedtuple('Constraint', ['kind', 'value'])
Expression = namedtuple('Expression', ['term1', 'operator', 'term2'])
Operation = namedtuple('Operation', ['quality', 'operation', 'expression', 'constraint'])
Predicate = namedtuple('Predicate', ['name', 'predicate'])
Rule = namedtuple('Rule', ['name', 'predicates', 'baggage'])
Pos = namedtuple('Pos', ['abs', 'line', 'column'])
Source = namedtuple('Source', ['start', 'end', 'text'])


class VALUE: pass
