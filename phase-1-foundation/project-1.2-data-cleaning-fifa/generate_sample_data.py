"""
Generate a synthetic FIFA-style player dataset with REALISTIC DIRT.

The real dataset ("FIFA 22 complete player dataset" on Kaggle) is messy in
systematic, explainable ways. This generator reproduces those exact mess
patterns so the cleaning pipeline has real work to do:

    * value / wage as currency strings:   "€105.5M", "€500K", "€0"
    * composite rating strings:           "90+2", "78-1", "85"
    * duplicated rows (same player exported twice)
    * inconsistent date formats in joined_date
    * missing values in club (free agents) and value
    * whitespace / casing noise in nationality

Output: data/raw/fifa_players_raw.csv
"""

import random
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
random.seed(SEED)
np.random.seed(SEED)

RAW_DIR = Path(__file__).parent / "data" / "raw"
N_PLAYERS = 3_000

FIRST = ["Lucas", "Marco", "Kylian", "Erling", "Mohamed", "Kevin", "Luka",
         "Sergio", "Joao", "Pedri", "Jamal", "Vinicius", "Bruno", "Harry",
         "Son", "Sadio", "Riyad", "Thiago", "Casemiro", "Rodri"]
LAST = ["Silva", "Rossi", "Mbewe", "Haaland", "Salah", "DeJong", "Modric",
        "Ramos", "Felix", "Gonzalez", "Musiala", "Junior", "Fernandes",
        "Kane", "Min", "Mane", "Mahrez", "Alcantara", "Santos", "Hernandez"]
NATIONS = ["Brazil", "France", "Germany", "Spain", "England", "Argentina",
           "Portugal", "Netherlands", "Italy", "Belgium"]
CLUBS = ["FC Aurora", "Real Vela", "Sporting Norte", "AC Ferro", "United Bay",
         "Olympique Sud", "Dynamo Ost", "Celtic Verde", "Inter Nova", None]
POSITIONS = ["GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST"]


def currency_string(v: float) -> str:
    """Format a number the way FIFA exports do: €105.5M / €500K / €0."""
    if v >= 1_000_000:
        return f"€{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"€{v / 1_000:.0f}K"
    return f"€{v:.0f}"


def composite_rating(base: int) -> str:
    """Some ratings carry a modifier: '90+2' means 92; a few are plain."""
    roll = random.random()
    if roll < 0.30:
        return f"{base}+{random.randint(1, 3)}"
    if roll < 0.35:
        return f"{base}-{random.randint(1, 2)}"
    return str(base)


def messy_date() -> str:
    """Three date formats mixed in the same column — a real Kaggle classic."""
    y = random.randint(2015, 2021)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    fmt = random.random()
    if fmt < 0.5:
        return f"{y}-{m:02d}-{d:02d}"        # ISO
    if fmt < 0.8:
        return f"{m}/{d}/{y}"                # US style
    return f"{d} {'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[m-1]} {y}"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for i in range(N_PLAYERS):
        overall = int(np.clip(np.random.normal(68, 8), 47, 94))
        value = max(0, np.random.lognormal(mean=13.5, sigma=1.4))
        wage = max(500, value / random.randint(300, 900))
        nationality = random.choice(NATIONS)
        # Whitespace/casing noise on ~8% of nationality values (validity issue)
        if random.random() < 0.08:
            nationality = f"  {nationality.upper()} "

        rows.append({
            "player_id": 100_000 + i,
            "short_name": f"{random.choice(FIRST)} {random.choice(LAST)}",
            "age": int(np.clip(np.random.normal(25, 4), 16, 42)),
            "nationality": nationality,
            "club": random.choice(CLUBS),               # None = free agent (valid state!)
            "position": random.choice(POSITIONS),
            "overall": composite_rating(overall),        # e.g. "90+2"
            "potential": composite_rating(min(96, overall + random.randint(0, 8))),
            "value_eur": currency_string(value) if random.random() > 0.03 else None,
            "wage_eur": currency_string(wage),
            "joined_date": messy_date(),
            "height_cm": int(np.clip(np.random.normal(181, 7), 158, 206)),
            "weight_kg": int(np.clip(np.random.normal(76, 7), 55, 105)),
        })

    df = pd.DataFrame(rows)

    # Inject exact-duplicate rows (~3%) — same player exported twice
    # (uniqueness issue).
    dupes = df.sample(frac=0.03, random_state=SEED)
    df = pd.concat([df, dupes], ignore_index=True)
    # Shuffle so duplicates aren't adjacent (realistic).
    df = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)

    out = RAW_DIR / "fifa_players_raw.csv"
    df.to_csv(out, index=False)
    print(f"wrote {out} — {len(df):,} rows ({len(dupes)} injected duplicates)")


if __name__ == "__main__":
    main()
