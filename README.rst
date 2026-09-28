Ravel
=====

Ravel is a tool for building Quality-Based Narratives (QBNs), as `pioneered`_ by
Failbetter Games, with a syntax inspired by Inkle Studios' `Ink`_ format and
YAML.

The goals of Ravel are manifold:

- Provide a flexible engine for authoring, testing, and running QBNs.
- Provide a simple, text-based authoring format that is easy to work with,
  yet doesn't require special tools.
- Export QBNs to a portable format that can be read from any environment.
- Provide a simple reference implementation of a VM that can perform a
  Ravel-based QBN.

.. _`pioneered`: http://www.failbettergames.com/storynexus-developer-diary-2-fewer-spreadsheets-less-swearing/

.. _`ink`: http://www.inklestudios.com/ink/

Installing
----------

Clone the repository::

    git clone https://github.com/eykd/ravel.git

Install `uv <https://docs.astral.sh/uv/>`_, then let it build the environment.
It fetches Python 3.14 itself, so there is nothing else to install::

    cd ravel
    uv sync

Test that everything works by running the demo::

    uv run ravel run examples/cloak

Running
-------

``ravel run`` compiles the story rooted at ``DIRECTORY`` and starts an interactive session at the
console::

    uv run ravel run examples/cloak

``--verbose`` narrates quality changes and situation entry/exit alongside the story text;
``--debug`` does the same and drops into ``pdb`` on an unexpected error. Both are group-level
flags, so they go before the subcommand::

    uv run ravel --verbose run examples/cloak

At the ``What'll it be? `` prompt, type a number to choose from the current menu, or one of the
in-game commands below.

Saving and loading
-------------------

From the running prompt:

- ``save`` — save to the default file (``ravel-save.json`` in the current directory).
- ``save FILE`` — save to ``FILE`` instead.
- ``load`` / ``load FILE`` — load a save, replacing the running game; a bad or missing file
  prints ``Could not load: ...`` and leaves the current game untouched.
- ``s`` — show the current qualities.
- ``help`` / ``?`` — list the commands above.
- ``q`` — quit.

To resume a saved game from the command line, pass ``--load`` when starting ``run``::

    uv run ravel run examples/cloak --load ravel-save.json

If the story has changed since the save was written (lines added, situations removed or
restructured), loading never fails outright: the engine resumes as close to the saved position as
the current story allows, dropping only the frames that no longer fit, and prints a line noting
where play resumed.
