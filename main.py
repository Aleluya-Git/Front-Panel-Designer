#!/usr/bin/env python3
"""Electronic Front Panel Designer — lanzador."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from efpd.gui.app import main
    sys.exit(main())
