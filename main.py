"""
Top-level entrypoint. Kept thin on purpose -- all real CLI logic lives in
cli/main.py (the relocated former src/main.py). Run as:

    python main.py [args]

or, after `pip install -e .`:

    cryptosight [args]
"""

from cli.main import main

if __name__ == "__main__":
    main()
