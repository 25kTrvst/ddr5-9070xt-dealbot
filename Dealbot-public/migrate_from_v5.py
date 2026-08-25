from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
target = root / ".env"
if target.exists():
    print("V6 .env already exists; nothing was overwritten.")
    raise SystemExit(0)
for sibling in sorted(root.parent.glob("*v5*"), reverse=True):
    source = sibling / ".env"
    if source.exists():
        shutil.copy2(source, target)
        print(f"Copied settings from {source}. Review V6's new optional fields in .env.example.")
        raise SystemExit(0)
print("No V5 .env found. Copy .env.example to .env and add your credentials.")
