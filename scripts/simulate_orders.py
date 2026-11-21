from __future__ import annotations

import argparse
import random
import sys

import requests


PRODUCT_IDS = ["P001", "P002", "P003", "P004", "P005", "P006"]


def simulate(base_url: str, count: int) -> None:
    session = requests.Session()
    for index in range(1, count + 1):
        selected = random.sample(PRODUCT_IDS, k=random.randint(1, 3))
        payload = {
            "user_id": f"sim-user-{index:03d}",
            "items": [
                {"product_id": product_id, "quantity": random.randint(1, 4)}
                for product_id in selected
            ],
        }
        response = session.post(f"{base_url}/api/orders", json=payload, timeout=15)
        response.raise_for_status()
        order = response.json()
        print(f"{index:03d}/{count}: {order['order_id']} -> SQS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Simula pedidos y los envía a la cola mediante la API")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count debe ser positivo")
    try:
        simulate(args.base_url.rstrip("/"), args.count)
        return 0
    except requests.RequestException as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
