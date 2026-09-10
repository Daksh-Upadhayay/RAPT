"""Build the ticket classification dataset: Bitext + templates, split 70/15/15.

Sources:
- Bitext customer-support dataset (CDLA-Sharing-1.0), downloaded to data/raw/ on first
  run. Intents mapped to our categories: track_order -> order_status;
  get_refund, track_refund, check_refund_policy -> refund_request; cancel_order ->
  cancellation. All other intents are off-domain and dropped.
- scripts/ticket_templates.py for all six categories (the only source for damaged_item,
  delivery_delay and product_question).

The split is grouped: every variant of one Bitext sentence skeleton or template core
sentence lands in the same split, so val/test measure performance on phrasings the
model hasn't seen, not on near-copies of training rows. It is still in-distribution;
data/eval/handwritten_test_set.csv is the out-of-distribution check.

Output: data/processed/tickets.csv with columns text, category, source, group, split.
Urgency is not stored here; train_urgency_model.py derives weak labels from the text.

Usage (from backend/):
    uv run python -m scripts.build_dataset
    uv run python -m scripts.build_dataset --per-class 900 --seed 42
"""

import argparse
import random
import re
import string
from pathlib import Path

import httpx
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from app.core.enums import TicketCategory as C
from scripts.ticket_templates import add_tone, generate, order_id

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BITEXT_PATH = DATA_DIR / "raw" / "bitext_customer_support.csv"
BITEXT_URL = (
    "https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset/"
    "resolve/main/Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"
)
OUTPUT_PATH = DATA_DIR / "processed" / "tickets.csv"

INTENT_TO_CATEGORY = {
    "track_order": C.ORDER_STATUS,
    "get_refund": C.REFUND_REQUEST,
    "track_refund": C.REFUND_REQUEST,
    "check_refund_policy": C.REFUND_REQUEST,
    "cancel_order": C.CANCELLATION,
}
BITEXT_SHARE = 0.5  # share of each Bitext-covered class that comes from Bitext
TONE_SHARE = 0.35  # share of Bitext rows that get a tone sentence appended
SPLIT_FOLDS = {"test": 3, "val": 3, "train": 14}  # of 20 grouped folds -> 15/15/70 %

_PLACEHOLDER = re.compile(r"\{\{([^}]+)\}\}")


def download_bitext() -> None:
    BITEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Bitext dataset to {BITEXT_PATH} ...")
    with httpx.stream("GET", BITEXT_URL, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with BITEXT_PATH.open("wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)


def fill_placeholders(text: str, rng: random.Random) -> str:
    values = {
        "Order Number": lambda: order_id(rng),
        "Refund Amount": lambda: str(rng.randint(15, 500)),
        "Currency Symbol": lambda: "$",
        "Person Name": lambda: rng.choice(["Sam", "Priya", "Jordan", "Maria"]),
    }
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), lambda: "")(), text)


def skeleton(text: str) -> str:
    """Group key for near-duplicate Bitext rows: lowercase, digits and punctuation removed."""
    text = re.sub(r"\d+", "0", text.lower())
    return " ".join(text.translate(str.maketrans("", "", string.punctuation)).split())


def load_bitext(rng: random.Random, tone: bool = True) -> pd.DataFrame:
    if not BITEXT_PATH.exists():
        download_bitext()
    raw = pd.read_csv(BITEXT_PATH)
    df = raw[raw["intent"].isin(INTENT_TO_CATEGORY)].copy()
    df["category"] = df["intent"].map(lambda i: str(INTENT_TO_CATEGORY[i]))
    df["group"] = "bitext:" + df["instruction"].map(skeleton)
    df = df.drop_duplicates(subset="group")  # keep one row per skeleton
    df["text"] = [fill_placeholders(t, rng) for t in df["instruction"]]
    if tone:
        df["text"] = [add_tone(t, rng) if rng.random() < TONE_SHARE else t for t in df["text"]]
    df["source"] = "bitext"
    return df[["text", "category", "source", "group"]]


def mix_sources(per_class: int, seed: int, rng: random.Random, tone: bool = True) -> pd.DataFrame:
    """`per_class` rows per category: Bitext where it covers the category, templates for the rest."""
    bitext = load_bitext(rng, tone=tone)
    parts = []
    for category in C:
        from_bitext = bitext[bitext["category"] == category]
        n_bitext = min(len(from_bitext), int(per_class * BITEXT_SHARE))
        from_bitext = from_bitext.sample(n=n_bitext, random_state=seed)
        seen = {t.lower().strip(string.punctuation + " ") for t in from_bitext["text"]}
        templates = pd.DataFrame(generate(category, per_class - n_bitext, rng, exclude=seen, tone=tone))
        parts += [from_bitext, templates]
    return pd.concat(parts, ignore_index=True)


def grouped_split(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Add a 70/15/15 `split` column, stratified by category, never splitting a `group`."""
    folds = StratifiedGroupKFold(n_splits=sum(SPLIT_FOLDS.values()), shuffle=True, random_state=seed)
    fold_of_row = pd.Series(-1, index=df.index)
    for fold, (_, idx) in enumerate(folds.split(df["text"], df["category"], groups=df["group"])):
        fold_of_row.iloc[idx] = fold
    boundaries = {"test": SPLIT_FOLDS["test"], "val": SPLIT_FOLDS["test"] + SPLIT_FOLDS["val"]}
    df["split"] = ["test" if f < boundaries["test"] else "val" if f < boundaries["val"] else "train" for f in fold_of_row]
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def build(per_class: int, seed: int) -> pd.DataFrame:
    return grouped_split(mix_sources(per_class, seed, random.Random(seed)), seed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-class", type=int, default=900)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = build(args.per_class, args.seed)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved {len(df)} rows to {OUTPUT_PATH}\n")
    print(pd.crosstab(df["category"], [df["split"]], margins=True).to_string(), "\n")
    print(pd.crosstab(df["category"], df["source"]).to_string(), "\n")
    leaked = df.groupby("group")["split"].nunique().gt(1).sum()
    print(f"groups spanning more than one split: {leaked}")


if __name__ == "__main__":
    main()
