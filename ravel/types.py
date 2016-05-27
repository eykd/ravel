from collections import namedtuple

Pos = namedtuple('Pos', ['abs', 'line', 'column'])
Source = namedtuple('Source', ['start', 'end', 'text'])
