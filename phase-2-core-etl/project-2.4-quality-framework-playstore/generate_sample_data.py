"""
Generate Google-Play-Store-style app data with quality problems to catch.

Mirrors the Kaggle "Google Play Store Apps" dataset shape (App, Category,
Rating, Reviews, Installs, Price, ...). Injects the specific defects a quality
framework should detect:

    * ratings out of range        (e.g. 19.0 — the famous real Play Store bug)
    * null app names              (completeness failure)
    * duplicate app rows          (uniqueness failure)
    * negative / non-numeric installs
    * a category not in the allowed set

Writes:
    data/raw/playstore_clean_batch.csv   mostly-good data (baseline)
    data/raw/playstore_bad_batch.csv     a "bad batch" (~10% volume) for the
                                         distributional/volume check demo
"""

import random
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 55
random.seed(SEED)
np.random.seed(SEED)

RAW_DIR = Path(__file__).parent / "data" / "raw"

CATEGORIES = ["GAME", "TOOLS", "BUSINESS", "LIFESTYLE", "FINANCE",
              "HEALTH_AND_FITNESS", "PHOTOGRAPHY", "SOCIAL", "PRODUCTIVITY"]
CONTENT_RATINGS = ["Everyone", "Teen", "Mature 17+", "Everyone 10+"]


def build_apps(n: int, start: int) -> pd.DataFrame:
    rows = []
    for i in range(start, start + n):
        rows.append({
            "app_id": i,
            "app_name": f"App {i}",
            "category": random.choice(CATEGORIES),
            "rating": round(np.clip(np.random.normal(4.1, 0.5), 1.0, 5.0), 1),
            "reviews": int(np.random.exponential(5000)),
            "installs": int(np.random.choice([1_000, 10_000, 100_000, 1_000_000])),
            "price": 0.0 if random.random() < 0.9 else round(random.uniform(0.99, 9.99), 2),
            "content_rating": random.choice(CONTENT_RATINGS),
        })
    return pd.DataFrame(rows)


def inject_defects(df: pd.DataFrame) -> pd.DataFrame:
    """Introduce known, countable quality defects for the framework to catch."""
    df = df.copy()
    idx = df.index.tolist()

    # 1. Rating out of range (the real Play Store "19.0" bug).
    bad_rating = random.sample(idx, 8)
    df.loc[bad_rating, "rating"] = [19.0, 6.5, -1.0, 5.5, 10.0, 7.7, 8.8, 6.1]

    # 2. Null app names (completeness).
    null_names = random.sample(idx, 5)
    df.loc[null_names, "app_name"] = None

    # 3. Negative installs (validity).
    neg_installs = random.sample(idx, 4)
    df.loc[neg_installs, "installs"] = -100

    # 4. A category outside the allowed set (validity / accepted values).
    bad_cat = random.sample(idx, 3)
    df.loc[bad_cat, "category"] = "UNKNOWN_CATEGORY"

    # 5. Duplicate rows (uniqueness) — append copies of a few apps.
    dupes = df.loc[random.sample(idx, 6)].copy()
    df = pd.concat([df, dupes], ignore_index=True)

    return df


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    clean = inject_defects(build_apps(2_000, start=1))
    clean.to_csv(RAW_DIR / "playstore_clean_batch.csv", index=False)
    print(f"wrote playstore_clean_batch.csv: {len(clean):,} rows (with injected defects)")

    # A "bad batch": only ~10% the usual volume — should trip the volume check.
    bad = inject_defects(build_apps(200, start=10_001))
    bad.to_csv(RAW_DIR / "playstore_bad_batch.csv", index=False)
    print(f"wrote playstore_bad_batch.csv:   {len(bad):,} rows (10% volume — trips the volume check)")


if __name__ == "__main__":
    main()
