"""Build the approved jelly PNG as RGB565 and refresh the Android pack."""
from pathlib import Path
import subprocess
subprocess.run(['node', str(Path(__file__).with_name('build_display_assets.js'))], check=True)
