"""Apply canonical mappings from a CSV to the database.

CSV format: source_alias, best_match, score, note

By default this script does a dry-run and prints what would be applied. Use --yes to actually insert rows into `canonical_mappings`.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "giocatori.db"
DEFAULT_CSV = ROOT / "suggested_canonical_mappings_highconf.csv"


def apply_csv(path: Path, yes: bool = False):
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Session = sessionmaker(bind=engine)
    session = Session()

    from app.models import CanonicalMapping

    rows = []
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)

    to_apply = []
    for r in rows:
        src = r.get("source_alias", "").strip()
        tgt = r.get("best_match", "").strip()
        score = float(r.get("score", 0) or 0)
        if not src or not tgt:
            continue
        # check existing
        exists = session.query(CanonicalMapping).filter(CanonicalMapping.variant == src).first()
        if exists:
            print(f"Skipping existing mapping: {src} -> {exists.canonical}")
            continue
        to_apply.append((src, tgt, score))

    if not to_apply:
        print("Nothing to apply.")
        return

    print("Planned mappings to apply:")
    for s, t, sc in to_apply:
        print(f"  {s} -> {t} (score={sc:.3f})")

    if not yes:
        print("Dry-run complete. Re-run with --yes to apply these mappings.")
        return

    # apply
    for s, t, sc in to_apply:
        cm = CanonicalMapping(variant=s, canonical=t)
        session.add(cm)
    session.commit()
    print(f"Applied {len(to_apply)} mappings.")


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="CSV file with suggestions")
    p.add_argument("--yes", action="store_true", help="Apply changes")
    args = p.parse_args()
    if not args.csv.exists():
        print(f"CSV file not found: {args.csv}")
    else:
        apply_csv(args.csv, yes=args.yes)
