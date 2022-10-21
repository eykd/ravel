from pyrsistent import pmap, pvector
from ravel import types
from ravel.compiler import effects


class TestCompileEffect:
    def test_it_should_compile_an_effect(self, env):
        effect = effects.compile_effect(env, "Situation", "test", "Quality += 1")
        expected = (types.Operation("Quality", "+=", 1, None), pmap())
        assert effect == expected

    def test_it_should_parse_an_effect_with_complex_expression(self, env):
        effect = effects.compile_effect(env, "Situation", "test", "Quality += value * 2")
        expected = (
            types.Operation(
                "Quality",
                "+=",
                types.Expression(types.VALUE, "*", 2),
                None,
            ),
            pmap(),
        )
        assert effect == expected


class TestCompileEffects:
    def test_it_should_compile_effects(self, env):
        effect = effects.compile_effects(env, "Situation", "test", ["Quality += 1", '"Other Quality" += 5'])
        expected = pvector(
            [
                (types.Operation("Quality", "+=", 1, None), pmap()),
                (types.Operation("Other Quality", "+=", 5, None), pmap()),
            ]
        )
        assert effect == expected
