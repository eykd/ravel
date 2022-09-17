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

Install Python 3.10. Create a Python virtual environment in the repo, and install the requirements::

    cd ravel
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

Test that everything works by running the demo::

    ravel run examples/cloak
