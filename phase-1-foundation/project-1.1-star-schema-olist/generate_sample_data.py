"""
Generate a synthetic Olist-style Brazilian e-commerce dataset.

The real dataset lives on Kaggle ("Brazilian E-Commerce Public Dataset by Olist")
and ships as 8 CSVs. This script produces the same 8 files with the same column
names and relationships, so build_star_schema.py works identically whether you
use this synthetic data or drop the real Kaggle CSVs into data/raw/.

Files produced (in data/raw/):
    olist_customers_dataset.csv
    olist_orders_dataset.csv
    olist_order_items_dataset.csv
    olist_products_dataset.csv
    olist_sellers_dataset.csv
    olist_order_payments_dataset.csv
    olist_order_reviews_dataset.csv
    olist_geolocation_dataset.csv
"""

import hashlib
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Reproducibility: same data every run, which also makes the loader idempotent
# to test against.
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

RAW_DIR = Path(__file__).parent / "data" / "raw"

N_CUSTOMERS = 2_000
N_SELLERS = 150
N_PRODUCTS = 500
N_ORDERS = 5_000

BRAZil_STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "PE"]
STATE_WEIGHTS = [0.42, 0.13, 0.12, 0.06, 0.05, 0.04, 0.04, 0.03, 0.03, 0.08]

CATEGORIES = [
    "cama_mesa_banho", "beleza_saude", "esporte_lazer", "moveis_decoracao",
    "informatica_acessorios", "utilidades_domesticas", "relogios_presentes",
    "telefonia", "ferramentas_jardim", "automotivo", "brinquedos",
    "cool_stuff", "perfumaria", "bebes", "eletronicos",
]

ORDER_STATUSES = ["delivered", "shipped", "canceled", "processing", "invoiced"]
STATUS_WEIGHTS = [0.90, 0.04, 0.03, 0.02, 0.01]

PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]
PAYMENT_WEIGHTS = [0.74, 0.19, 0.04, 0.03]


def fake_id(prefix: str, n: int) -> str:
    """Olist IDs are 32-char hex strings; mimic that with an MD5 hash."""
    return hashlib.md5(f"{prefix}-{n}".encode()).hexdigest()


def random_timestamp(start: datetime, end: datetime) -> datetime:
    """Uniformly random timestamp between two datetimes."""
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def build_customers() -> pd.DataFrame:
    states = np.random.choice(BRAZil_STATES, size=N_CUSTOMERS, p=STATE_WEIGHTS)
    return pd.DataFrame({
        "customer_id": [fake_id("cust", i) for i in range(N_CUSTOMERS)],
        # customer_unique_id: the *person*; customer_id is per-order in real Olist.
        "customer_unique_id": [fake_id("uniq", i % 1_800) for i in range(N_CUSTOMERS)],
        "customer_zip_code_prefix": np.random.randint(1000, 99999, size=N_CUSTOMERS),
        "customer_city": [f"city_{s.lower()}_{random.randint(1, 30)}" for s in states],
        "customer_state": states,
    })


def build_sellers() -> pd.DataFrame:
    states = np.random.choice(BRAZil_STATES, size=N_SELLERS, p=STATE_WEIGHTS)
    return pd.DataFrame({
        "seller_id": [fake_id("sell", i) for i in range(N_SELLERS)],
        "seller_zip_code_prefix": np.random.randint(1000, 99999, size=N_SELLERS),
        "seller_city": [f"city_{s.lower()}_{random.randint(1, 30)}" for s in states],
        "seller_state": states,
    })


def build_products() -> pd.DataFrame:
    df = pd.DataFrame({
        "product_id": [fake_id("prod", i) for i in range(N_PRODUCTS)],
        "product_category_name": np.random.choice(CATEGORIES, size=N_PRODUCTS),
        "product_name_lenght": np.random.randint(20, 70, size=N_PRODUCTS),
        "product_description_lenght": np.random.randint(100, 4000, size=N_PRODUCTS),
        "product_photos_qty": np.random.randint(1, 8, size=N_PRODUCTS),
        "product_weight_g": np.random.randint(50, 30000, size=N_PRODUCTS),
        "product_length_cm": np.random.randint(10, 100, size=N_PRODUCTS),
        "product_height_cm": np.random.randint(2, 80, size=N_PRODUCTS),
        "product_width_cm": np.random.randint(5, 60, size=N_PRODUCTS),
    })
    # Real Olist has ~1.8% products with missing category — reproduce that
    # so the loader has to handle nulls (late-arriving-dimension practice).
    missing = df.sample(frac=0.02, random_state=SEED).index
    df.loc[missing, "product_category_name"] = None
    return df


def build_orders(customers: pd.DataFrame) -> pd.DataFrame:
    start = datetime(2017, 1, 1)
    end = datetime(2018, 8, 31)
    rows = []
    for i in range(N_ORDERS):
        purchase = random_timestamp(start, end)
        status = np.random.choice(ORDER_STATUSES, p=STATUS_WEIGHTS)
        approved = purchase + timedelta(hours=random.randint(0, 48))
        carrier = approved + timedelta(days=random.randint(1, 5))
        delivered = carrier + timedelta(days=random.randint(1, 25))
        estimated = purchase + timedelta(days=random.randint(10, 40))
        rows.append({
            "order_id": fake_id("order", i),
            "customer_id": customers["customer_id"].iloc[i % N_CUSTOMERS],
            "order_status": status,
            "order_purchase_timestamp": purchase,
            "order_approved_at": approved if status != "canceled" else None,
            "order_delivered_carrier_date": carrier if status in ("delivered", "shipped") else None,
            # Only delivered orders have a delivery timestamp — a *structural*
            # null, exactly like the real dataset.
            "order_delivered_customer_date": delivered if status == "delivered" else None,
            "order_estimated_delivery_date": estimated,
        })
    return pd.DataFrame(rows)


def build_order_items(orders: pd.DataFrame, products: pd.DataFrame,
                      sellers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for order_id in orders["order_id"]:
        # Most orders have 1 item; a long tail has up to 5 (matches real Olist).
        n_items = np.random.choice([1, 2, 3, 4, 5], p=[0.88, 0.07, 0.03, 0.01, 0.01])
        for item_no in range(1, n_items + 1):
            rows.append({
                "order_id": order_id,
                "order_item_id": item_no,
                "product_id": products["product_id"].iloc[random.randint(0, N_PRODUCTS - 1)],
                "seller_id": sellers["seller_id"].iloc[random.randint(0, N_SELLERS - 1)],
                "shipping_limit_date": None,  # filled below
                "price": round(np.random.lognormal(mean=4.3, sigma=0.9), 2),
                "freight_value": round(np.random.lognormal(mean=2.7, sigma=0.5), 2),
            })
    df = pd.DataFrame(rows)
    df["shipping_limit_date"] = pd.Timestamp("2018-01-01")
    return df


def build_payments(orders: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    order_totals = items.groupby("order_id")[["price", "freight_value"]].sum().sum(axis=1)
    rows = []
    for order_id, total in order_totals.items():
        rows.append({
            "order_id": order_id,
            "payment_sequential": 1,
            "payment_type": np.random.choice(PAYMENT_TYPES, p=PAYMENT_WEIGHTS),
            "payment_installments": int(np.random.choice([1, 2, 3, 4, 6, 10],
                                                         p=[0.5, 0.13, 0.12, 0.1, 0.1, 0.05])),
            "payment_value": round(total, 2),
        })
    return pd.DataFrame(rows)


def build_reviews(orders: pd.DataFrame) -> pd.DataFrame:
    # ~80% of orders get a review, like the real dataset.
    reviewed = orders.sample(frac=0.8, random_state=SEED)
    return pd.DataFrame({
        "review_id": [fake_id("rev", i) for i in range(len(reviewed))],
        "order_id": reviewed["order_id"].values,
        "review_score": np.random.choice([1, 2, 3, 4, 5], size=len(reviewed),
                                         p=[0.10, 0.04, 0.08, 0.19, 0.59]),
        "review_comment_title": None,
        "review_comment_message": None,
        "review_creation_date": reviewed["order_purchase_timestamp"].values,
        "review_answer_timestamp": reviewed["order_purchase_timestamp"].values,
    })


def build_geolocation() -> pd.DataFrame:
    n = 1_000
    states = np.random.choice(BRAZil_STATES, size=n, p=STATE_WEIGHTS)
    return pd.DataFrame({
        "geolocation_zip_code_prefix": np.random.randint(1000, 99999, size=n),
        "geolocation_lat": np.random.uniform(-33.0, 2.0, size=n),
        "geolocation_lng": np.random.uniform(-73.0, -34.0, size=n),
        "geolocation_city": [f"city_{s.lower()}_{random.randint(1, 30)}" for s in states],
        "geolocation_state": states,
    })


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    customers = build_customers()
    sellers = build_sellers()
    products = build_products()
    orders = build_orders(customers)
    items = build_order_items(orders, products, sellers)
    payments = build_payments(orders, items)
    reviews = build_reviews(orders)
    geo = build_geolocation()

    datasets = {
        "olist_customers_dataset.csv": customers,
        "olist_sellers_dataset.csv": sellers,
        "olist_products_dataset.csv": products,
        "olist_orders_dataset.csv": orders,
        "olist_order_items_dataset.csv": items,
        "olist_order_payments_dataset.csv": payments,
        "olist_order_reviews_dataset.csv": reviews,
        "olist_geolocation_dataset.csv": geo,
    }
    for filename, df in datasets.items():
        path = RAW_DIR / filename
        df.to_csv(path, index=False)
        print(f"wrote {path.name:45s} {len(df):>7,} rows")


if __name__ == "__main__":
    main()
