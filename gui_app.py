"""Root entry point for Google Photos Backup & Sync Desktop GUI."""

import sys
import os

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from gui.app import main

if __name__ == "__main__":
    main()
