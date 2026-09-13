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
