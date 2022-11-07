from syml.types import Source


def source(text):
    return Source.from_text(text, text)


class Any:
    def __eq__(self, other):
        return True
