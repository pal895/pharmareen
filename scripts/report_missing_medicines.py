from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TRAINING_DIR = ROOT_DIR / "training"
DEFAULT_REPORT_PATH = ROOT_DIR / "MISSING_MEDICINES_REPORT.txt"


COMMON_KENYA_MEDICINES = [
    "Acyclovir",
    "Albendazole",
    "Amitriptyline",
    "Amlodipine",
    "Artemether Lumefantrine",
    "Aspirin",
    "Atenolol",
    "Azithromycin",
    "Betamethasone",
    "Brufen",
    "Cefixime",
    "Ceftriaxone",
    "Chloramphenicol",
    "Ciprofloxacin",
    "Clotrimazole",
    "Diclofenac",
    "Doxycycline",
    "Erythromycin",
    "Fluconazole",
    "Folic Acid",
    "Hydrocortisone",
    "Ibuprofen",
    "Loperamide",
    "Loratadine",
    "Losartan",
    "Metformin",
    "Metronidazole",
    "Omeprazole",
    "Prednisolone",
    "Salbutamol",
    "Septrin",
    "Zinc",
]


def build_missing_medicines_report(
    training_dir: str | Path = DEFAULT_TRAINING_DIR,
    common_medicines: list[str] | None = None,
) -> tuple[str, list[str]]:
    training_path = Path(training_dir)
    common = common_medicines or COMMON_KENYA_MEDICINES
    known = collect_known_medicine_terms(training_path)
    missing = [medicine for medicine in common if normalize_term(medicine) not in known]

    lines = [
        "PHARMAREEN MISSING MEDICINES REPORT",
        "",
        "Purpose:",
        "Identify likely common pharmacy medicines absent from the current Phase 1 brain.",
        "",
        f"Known medicine terms found: {len(known)}",
        f"Likely common medicines missing: {len(missing)}",
        "",
        "COPY-PASTE LIST:",
    ]
    lines.extend(f"- {medicine}" for medicine in missing)
    lines.extend(
        [
            "",
            "Build flow:",
            "- This report is informational only.",
            "- Do not stop Phase 1 because medicines are missing.",
            "- Onboarding can add or approve these manually later.",
        ]
    )
    return "\n".join(lines) + "\n", missing


def collect_known_medicine_terms(training_dir: Path) -> set[str]:
    known: set[str] = set()
    profiles = load_json(training_dir / "medicine_profiles.json", default={"medicines": []})
    for item in profiles.get("medicines", []):
        if not isinstance(item, dict):
            continue
        add_term(known, item.get("name"))
        for field in ("aliases", "generic_names"):
            for value in item.get(field, []):
                add_term(known, value)

    aliases = load_json(training_dir / "aliases.json", default={})
    for alias, medicine_name in aliases.get("medicine_aliases", {}).items():
        add_term(known, alias)
        add_term(known, medicine_name)

    corrections = load_json(training_dir / "corrections.json", default={})
    for memory in corrections.get("pharmacies", {}).values():
        if not isinstance(memory, dict):
            continue
        for alias, medicine_name in memory.get("medicine_aliases", {}).items():
            add_term(known, alias)
            add_term(known, medicine_name)

    for row in load_jsonl(training_dir / "pharmacy_examples.jsonl"):
        expected = row.get("expected")
        if isinstance(expected, dict):
            add_term(known, expected.get("medicine_name"))

    return known


def write_missing_medicines_report(
    training_dir: str | Path = DEFAULT_TRAINING_DIR,
    output_path: str | Path = DEFAULT_REPORT_PATH,
) -> tuple[Path, list[str]]:
    report, missing = build_missing_medicines_report(training_dir)
    path = Path(output_path)
    path.write_text(report, encoding="utf-8")
    return path, missing


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean:
            continue
        value = json.loads(clean)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def add_term(known: set[str], value: Any) -> None:
    normalized = normalize_term(value)
    if normalized:
        known.add(normalized)


def normalize_term(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PharMareen missing medicines report.")
    parser.add_argument("--training-dir", default=str(DEFAULT_TRAINING_DIR))
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()

    path, missing = write_missing_medicines_report(args.training_dir, args.output)
    print(f"Saved missing medicines report: {path}")
    print(f"Missing medicines listed: {len(missing)}")
    print("COPY-PASTE LIST:")
    for medicine in missing:
        print(f"- {medicine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
