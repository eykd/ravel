from collections import namedtuple

Pos = namedtuple('Pos', ['abs', 'line', 'column'])
BaseSource = namedtuple('Source', ['start', 'end', 'text'])


class Source(BaseSource):
    def __repr__(self):
        return 'Line %s, Column %s (index %s): %r' % (
            self.start.line, self.start.column, self.start.abs, self.text
        )
