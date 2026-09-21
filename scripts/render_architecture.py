from pathlib import Path

import cairosvg


ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "docs" / "system_architecture.svg"
target = ROOT / "docs" / "system_architecture.png"

cairosvg.svg2png(
    bytestring=source.read_bytes(),
    write_to=str(target),
    output_width=1600,
    output_height=900,
)
print(target)
