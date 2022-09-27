from syml.utils import get_text_source


def source(text):
    return get_text_source(text, text)


class Any:
    def __eq__(self, other):
        return True
