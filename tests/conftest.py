import os
import sys
from pathlib import Path

# Get the project root directory
project_root = str(Path(__file__).parent.parent)

# Add the project root to Python path
sys.path.append(project_root)