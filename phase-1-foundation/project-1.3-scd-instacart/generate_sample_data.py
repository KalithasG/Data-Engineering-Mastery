"""
Generate Instacart-style product catalog SNAPSHOTS for the SCD project.

The real dataset ("Instacart Market Basket Analysis" on Kaggle) is a static
snapshot: products.csv, aisles.csv, departments.csv, orders.csv. SCD only
makes sense when data CHANGES over time, so this generator produces three
monthly snapshots of the product catalog, mutating a slice of products
between snapshots — exactly what a nightly extract from the source system
would deliver.

Mutations between snapshots (the changes SCD must track):
    * some products move to a different aisle/department  (re-categorisation)
    * some products change price                          (price updates)
    * some product names get typo fixes                   (Type 1 material!)
    * a few brand-new products appear                     (inserts)

Output (data/raw/):
    products_snapshot_2023-01-01.csv
    products_snapshot_2023-02-01.csv
    products_snapshot_2023-03-01.csv
    orders.csv          (order facts spread across the three months)
"""

import random
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 99
random.seed(SEED)
np.random.seed(SEED)

RAW_DIR = Path(__file__).parent / "data" / "raw"
N_PRODUCTS = 400
N_ORDERS = 3_000

DEPARTMENTS = {
    1: "produce", 2: "dairy eggs", 3: "snacks", 4: "beverages",
    5: "frozen", 6: "pantry", 7: "bakery", 8: "household",
}
AISLES = {
    1: ("fresh fruits", 1), 2: ("fresh vegetables", 1),
    3: ("milk", 2), 4: ("yogurt", 2), 5: ("cheese", 2),
    6: ("chips pretzels", 3), 7: ("candy chocolate", 3),
    8: ("soft drinks", 4), 9: ("coffee", 4),
    10: ("frozen meals", 5), 11: ("ice cream", 5),
    12: ("pasta sauce", 6), 13: ("baking supplies", 6),
    14: ("bread", 7), 15: ("cleaning products", 8),
}

ADJ = ["Organic", "Classic", "Premium", "Family Size", "Fresh", "Natural"]
NOUN = ["Bananas", "Whole Milk", "Cheddar", "Tortilla Chips", "Cola",
        "Pasta Sauce", "Sourdough", "Greek Yogurt", "Coffee Beans",
        "Ice Cream", "Dish Soap", "Baby Spinach", "Dark Chocolate",
        "Frozen Pizza", "Sparkling Water", "Granola"]


def base_catalog() -> pd.DataFrame:
    """Snapshot 1: the initial product catalog."""
    rows = []
    for pid in range(1, N_PRODUCTS + 1):
        aisle_id = random.choice(list(AISLES.keys()))
        aisle_name, dept_id = AISLES[aisle_id]
        rows.append({
            "product_id": pid,                       # business (natural) key
            "product_name": f"{random.choice(ADJ)} {random.choice(NOUN)} #{pid}",
            "aisle": aisle_name,
            "department": DEPARTMENTS[dept_id],
            "unit_price": round(np.random.uniform(0.99, 24.99), 2),
        })
    return pd.DataFrame(rows)


def mutate(snapshot: pd.DataFrame, n_new_start: int) -> pd.DataFrame:
    """Produce the next monthly snapshot: mutate ~15% of rows, add 5 products."""
    df = snapshot.copy()

    # 1) Re-categorisation: 5% of products move aisle+department.
    move = df.sample(frac=0.05, random_state=random.randint(0, 10_000)).index
    for idx in move:
        aisle_id = random.choice(list(AISLES.keys()))
        aisle_name, dept_id = AISLES[aisle_id]
        df.loc[idx, ["aisle", "department"]] = [aisle_name, DEPARTMENTS[dept_id]]

    # 2) Price changes: 8% of products.
    reprice = df.sample(frac=0.08, random_state=random.randint(0, 10_000)).index
    df.loc[reprice, "unit_price"] = (
        df.loc[reprice, "unit_price"] * np.random.uniform(0.85, 1.25, size=len(reprice))
    ).round(2)

    # 3) Typo fixes: 2% of names get a trailing marker removed/normalised.
    #    (In the real world: 'Organic Bananas!!' -> 'Organic Bananas'.)
    fix = df.sample(frac=0.02, random_state=random.randint(0, 10_000)).index
    df.loc[fix, "product_name"] = df.loc[fix, "product_name"].str.replace(
        r"\s*#(\d+)$", r" No.\1", regex=True)

    # 4) Five brand-new products appear.
    new_rows = []
    for pid in range(n_new_start, n_new_start + 5):
        aisle_id = random.choice(list(AISLES.keys()))
        aisle_name, dept_id = AISLES[aisle_id]
        new_rows.append({
            "product_id": pid,
            "product_name": f"{random.choice(ADJ)} {random.choice(NOUN)} #{pid}",
            "aisle": aisle_name,
            "department": DEPARTMENTS[dept_id],
            "unit_price": round(np.random.uniform(0.99, 24.99), 2),
        })
    return pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)


def build_orders(max_product_id: int) -> pd.DataFrame:
    """Order facts spread across Jan-Mar 2023, referencing product_ids."""
    dates = pd.to_datetime(np.random.choice(
        pd.date_range("2023-01-01", "2023-03-28"), size=N_ORDERS))
    return pd.DataFrame({
        "order_id": range(1, N_ORDERS + 1),
        "product_id": np.random.randint(1, max_product_id + 1, size=N_ORDERS),
        "quantity": np.random.randint(1, 6, size=N_ORDERS),
        "order_date": dates.date,
    })


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    snap1 = base_catalog()
    snap2 = mutate(snap1, n_new_start=N_PRODUCTS + 1)
    snap3 = mutate(snap2, n_new_start=N_PRODUCTS + 6)

    for date, snap in [("2023-01-01", snap1), ("2023-02-01", snap2),
                       ("2023-03-01", snap3)]:
        path = RAW_DIR / f"products_snapshot_{date}.csv"
        snap.to_csv(path, index=False)
        print(f"wrote {path.name}: {len(snap)} products")

    orders = build_orders(max_product_id=N_PRODUCTS)  # orders only for original products
    orders.to_csv(RAW_DIR / "orders.csv", index=False)
    print(f"wrote orders.csv: {len(orders)} order lines")


if __name__ == "__main__":
    main()
