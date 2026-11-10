"""Print Windows PE imports and whether each dependency is packaged."""

from __future__ import annotations

import sys
from pathlib import Path

import pefile


def imports(path: Path) -> list[str]:
    image = pefile.PE(str(path), fast_load=True)
    image.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
    )
    return sorted(
        entry.dll.decode("ascii", errors="replace")
        for entry in getattr(image, "DIRECTORY_ENTRY_IMPORT", [])
    )


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    internal = root / "_internal"
    openbabel = internal / "tools" / "openbabel"
    targets = [openbabel / "obabel.exe", *openbabel.glob("*.obf")]
    available: dict[str, list[Path]] = {}
    for candidate in root.rglob("*"):
        if candidate.is_file():
            available.setdefault(candidate.name.lower(), []).append(candidate)
    for target in targets:
        print(f"PE IMPORTS: {target.relative_to(root)}")
        for dependency in imports(target):
            matches = available.get(dependency.lower(), [])
            location = ", ".join(str(path.relative_to(root)) for path in matches) or "NOT PACKAGED"
            print(f"  {dependency}: {location}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
