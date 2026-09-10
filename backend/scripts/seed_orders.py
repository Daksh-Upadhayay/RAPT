"""Seed the customers and orders tables with realistic fake e-commerce data.

Order dates are generated relative to today, and each order's status is kept
consistent with its dates and tracking number (e.g. a `delayed` order is past its
expected delivery date; a `processing` order has no tracking number yet).

Usage (from backend/):
    uv run python -m scripts.seed_orders                     # 200 customers
    uv run python -m scripts.seed_orders --customers 50 --seed 7
    uv run python -m scripts.seed_orders --reset             # wipe customers/orders (and tickets) first
"""

import argparse
import asyncio
import random
import string
import uuid
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from faker import Faker
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal, engine
from app.core.enums import OrderStatus
from app.models import Customer, Order

# (item name, min price, max price) in dollars
CATALOG: list[tuple[str, int, int]] = [
    ("Wireless Headphones", 40, 250),
    ("Bluetooth Speaker", 25, 180),
    ("Blender", 30, 150),
    ("Coffee Maker", 35, 220),
    ("Air Fryer", 50, 160),
    ("Electric Kettle", 20, 80),
    ("Kitchen Scale", 12, 45),
    ("Office Chair", 90, 450),
    ("Laptop Stand", 20, 70),
    ("Desk Lamp", 15, 90),
    ("Bookshelf", 60, 300),
    ("Wireless Mouse", 15, 90),
    ("Mechanical Keyboard", 50, 200),
    ("Phone Case", 8, 40),
    ("Smartwatch", 120, 400),
    ("Camera Tripod", 25, 150),
    ("Running Shoes", 60, 180),
    ("Winter Jacket", 80, 350),
    ("Backpack", 30, 140),
    ("Yoga Mat", 15, 80),
    ("Water Bottle", 10, 45),
    ("Throw Blanket", 20, 90),
    ("Picture Frame", 10, 60),
    ("Board Game", 20, 70),
    ("Toolset", 30, 200),
    ("Garden Hose", 20, 75),
    ("Night Lamp", 12, 50),
    ("Robot Vacuum", 150, 600),
]

STATUS_WEIGHTS: dict[OrderStatus, int] = {
    OrderStatus.DELIVERED: 45,
    OrderStatus.SHIPPED: 20,
    OrderStatus.PROCESSING: 15,
    OrderStatus.DELAYED: 10,
    OrderStatus.CANCELLED: 10,
}

TRACKING_CHARS = string.digits + string.ascii_uppercase


class ExistingDataError(Exception):
    """Refusing to seed on top of existing customers/orders without --reset."""


def make_order(fake: Faker, rng: random.Random, customer_id: uuid.UUID, today: date) -> Order:
    item_name, low, high = rng.choice(CATALOG)
    status = rng.choices(list(STATUS_WEIGHTS), weights=list(STATUS_WEIGHTS.values()))[0]

    def days_ago(lo: int, hi: int) -> date:
        return today - timedelta(days=rng.randint(lo, hi))

    def plus_days(d: date, lo: int, hi: int) -> date:
        return d + timedelta(days=rng.randint(lo, hi))

    tracking_number: str | None = fake.bothify("1Z" + "?" * 16, letters=TRACKING_CHARS)
    expected_delivery: date | None
    match status:
        case OrderStatus.PROCESSING:  # not shipped yet: no tracking, delivery in the future
            order_date = days_ago(0, 2)
            expected_delivery = plus_days(order_date, 5, 8)
            tracking_number = None
        case OrderStatus.SHIPPED:  # in transit, still on schedule
            order_date = days_ago(1, 3)
            expected_delivery = plus_days(order_date, 4, 7)
        case OrderStatus.DELIVERED:
            order_date = days_ago(8, 60)
            expected_delivery = plus_days(order_date, 3, 7)
        case OrderStatus.DELAYED:  # past its expected delivery date
            order_date = days_ago(9, 20)
            expected_delivery = plus_days(order_date, 3, 7)
        case OrderStatus.CANCELLED:
            order_date = days_ago(1, 60)
            expected_delivery = None
            tracking_number = None

    return Order(
        customer_id=customer_id,
        item_name=item_name,
        status=status,
        tracking_number=tracking_number,
        amount=Decimal(rng.randint(low * 100, high * 100)) / 100,
        order_date=order_date,
        expected_delivery=expected_delivery,
    )


async def seed(
    session: AsyncSession,
    n_customers: int = 200,
    seed: int = 42,
    today: date | None = None,
    reset: bool = False,
) -> tuple[int, list[Order]]:
    today = today or date.today()
    fake = Faker("en_US")
    fake.seed_instance(seed)
    rng = random.Random(seed)

    if reset:
        # CASCADE also clears tickets and everything hanging off them
        await session.execute(text("TRUNCATE customers, orders CASCADE"))
    elif await session.scalar(select(func.count()).select_from(Customer)):
        raise ExistingDataError("customers table is not empty; rerun with --reset to wipe and reseed")

    customers = [Customer(name=fake.name(), email=fake.unique.email()) for _ in range(n_customers)]
    session.add_all(customers)
    await session.flush()  # populates server-generated customer ids

    orders = [
        make_order(fake, rng, customer.id, today) for customer in customers for _ in range(rng.randint(1, 5))
    ]
    session.add_all(orders)
    await session.commit()
    return len(customers), orders


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--customers", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true", help="truncate customers/orders (and tickets) first")
    args = parser.parse_args()

    try:
        async with SessionLocal() as session:
            n_customers, orders = await seed(session, args.customers, args.seed, reset=args.reset)
    except ExistingDataError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    finally:
        await engine.dispose()

    print(f"Seeded {n_customers} customers and {len(orders)} orders")
    for status, count in Counter(o.status for o in orders).most_common():
        print(f"  {status:<11} {count}")
    print(f"  orders over $100: {sum(o.amount > 100 for o in orders)}")


if __name__ == "__main__":
    asyncio.run(main())
