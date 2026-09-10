"""Build the urgency training corpus (v2): issue-only tickets wrapped in varied urgency phrasing.

The base tickets come from the same sources as the category dataset (Bitext + templates),
built without their tone sentences. Each base ticket then gets `--variants` different
urgency wrappings from scripts/urgency_phrases.py. Urgency is still not stored:
train_urgency_model.py labels it with the weak-supervision rules.

The split is grouped by base sentence, so all wrappings of one ticket (and all variants
of one template sentence) land in the same split.

Output: data/processed/urgency_tickets.csv with columns text, category, source, group, split.

Usage (from backend/):
    uv run python -m scripts.build_urgency_dataset
"""

import argparse
import random

import pandas as pd

from scripts.build_dataset import DATA_DIR, grouped_split, mix_sources
from scripts.urgency_phrases import compose

OUTPUT_PATH = DATA_DIR / "processed" / "urgency_tickets.csv"


def build(per_class: int, variants: int, seed: int) -> pd.DataFrame:
    rng = random.Random(seed)
    base = mix_sources(per_class, seed, rng, tone=False)
    rows = [row | {"text": compose(row["text"], rng)} for row in base.to_dict("records") for _ in range(variants)]
    df = pd.DataFrame(rows).drop_duplicates(subset="text").reset_index(drop=True)
    return grouped_split(df, seed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-class", type=int, default=900)
    parser.add_argument("--variants", type=int, default=2, help="urgency wrappings per base ticket")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    df = build(args.per_class, args.variants, args.seed)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT_PATH}")
    print(df["split"].value_counts().to_string())
    print(f"groups spanning more than one split: {df.groupby('group')['split'].nunique().gt(1).sum()}")


if __name__ == "__main__":
    main()
