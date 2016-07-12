from ravel import types


def source(text):
    length = len(text)
    return types.Source(
        types.Pos(0, 1, 1),
        types.Pos(length, length + 1, length + 1),
        text
    )
