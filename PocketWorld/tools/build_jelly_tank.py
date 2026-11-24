"""Regenerate the code-authored RGB565 backdrop; run before the JS pack builder."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'firmware'))
from jelly_tank import background

(root / 'firmware' / 'assets' / 'jellyfish-tank.dat').write_bytes(background())
print('Built quiet single-jelly tank: 240 x 240 RGB565')
