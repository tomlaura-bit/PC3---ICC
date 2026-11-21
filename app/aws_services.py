from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import BinaryIO

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.config import Config


AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
PRODUCTS_TABLE = os.getenv("PRODUCTS_TABLE", "pc3-products")
ORDERS_TABLE = os.getenv("ORDERS_TABLE", "pc3-orders")
USER_IMAGES_BUCKET = os.getenv("USER_IMAGES_BUCKET", "pc3-user-images")
ORDERS_QUEUE = os.getenv("ORDERS_QUEUE", "pc3-orders-queue")

CLIENT_CONFIG = Config(
    retries={"total_max_attempts": 3, "mode": "standard"},
    connect_timeout=3,
    read_timeout=10,
)
S3_CONFIG = CLIENT_CONFIG.merge(Config(s3={"addressing_style": "path"}))

session = boto3.Session(region_name=AWS_REGION)
dynamodb = session.resource("dynamodb", endpoint_url=AWS_ENDPOINT_URL, config=CLIENT_CONFIG)
s3 = session.client("s3", endpoint_url=AWS_ENDPOINT_URL, config=S3_CONFIG)
sqs = session.client("sqs", endpoint_url=AWS_ENDPOINT_URL, config=CLIENT_CONFIG)

products_table = dynamodb.Table(PRODUCTS_TABLE)
orders_table = dynamodb.Table(ORDERS_TABLE)

CATALOG = [
    {"product_id": "P001", "name": "Teclado mecánico", "price": Decimal("189.90"), "category": "Periféricos"},
    {"product_id": "P002", "name": "Mouse inalámbrico", "price": Decimal("79.90"), "category": "Periféricos"},
    {"product_id": "P003", "name": "Audífonos USB", "price": Decimal("129.50"), "category": "Audio"},
    {"product_id": "P004", "name": "Webcam HD", "price": Decimal("149.00"), "category": "Video"},
    {"product_id": "P005", "name": "Hub USB-C", "price": Decimal("99.90"), "category": "Accesorios"},
    {"product_id": "P006", "name": "Soporte para laptop", "price": Decimal("119.00"), "category": "Accesorios"},
]


def _create_table_if_missing(table_name: str, key_name: str) -> None:
    existing = dynamodb.meta.client.list_tables().get("TableNames", [])
    if table_name in existing:
        return
    dynamodb.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": key_name, "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": key_name, "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb.meta.client.get_waiter("table_exists").wait(
        TableName=table_name,
        WaiterConfig={"Delay": 1, "MaxAttempts": 20},
    )


def ensure_resources() -> dict[str, str]:
    _create_table_if_missing(PRODUCTS_TABLE, "product_id")
    _create_table_if_missing(ORDERS_TABLE, "order_id")

    bucket_names = {bucket["Name"] for bucket in s3.list_buckets().get("Buckets", [])}
    if USER_IMAGES_BUCKET not in bucket_names:
        s3.create_bucket(Bucket=USER_IMAGES_BUCKET)

    try:
        queue_url = sqs.get_queue_url(QueueName=ORDERS_QUEUE)["QueueUrl"]
    except sqs.exceptions.QueueDoesNotExist:
        queue_url = sqs.create_queue(QueueName=ORDERS_QUEUE)["QueueUrl"]

    with products_table.batch_writer(overwrite_by_pkeys=["product_id"]) as batch:
        for product in CATALOG:
            batch.put_item(Item=product)

    return {
        "products_table": PRODUCTS_TABLE,
        "orders_table": ORDERS_TABLE,
        "bucket": USER_IMAGES_BUCKET,
        "queue_url": queue_url,
    }


def wait_for_resources(max_attempts: int = 30) -> dict[str, str]:
    last_error: Exception | None = None
    for _ in range(max_attempts):
        try:
            return ensure_resources()
        except Exception as error:
            last_error = error
            time.sleep(2)
    if last_error:
        raise last_error
    raise RuntimeError("No se pudieron inicializar los recursos")


def _json_value(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral() else float(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def list_products() -> list[dict]:
    response = products_table.scan()
    products = sorted(response.get("Items", []), key=lambda item: item["product_id"])
    return _json_value(products)


def create_order(user_id: str, requested_items: list[dict]) -> dict:
    if not requested_items:
        raise ValueError("El carrito está vacío")

    order_items = []
    total = Decimal("0")
    for requested in requested_items:
        product_id = requested["product_id"]
        quantity = int(requested["quantity"])
        if quantity < 1 or quantity > 20:
            raise ValueError("La cantidad debe estar entre 1 y 20")
        product = products_table.get_item(Key={"product_id": product_id}).get("Item")
        if not product:
            raise ValueError(f"Producto inexistente: {product_id}")
        subtotal = product["price"] * quantity
        total += subtotal
        order_items.append(
            {
                "product_id": product_id,
                "name": product["name"],
                "quantity": quantity,
                "unit_price": product["price"],
                "subtotal": subtotal,
            }
        )

    order = {
        "order_id": str(uuid.uuid4()),
        "user_id": user_id.strip() or "cliente-demo",
        "items": order_items,
        "total": total,
        "status": "PENDIENTE",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    orders_table.put_item(
        Item=order,
        ConditionExpression=Attr("order_id").not_exists(),
    )

    queue_url = sqs.get_queue_url(QueueName=ORDERS_QUEUE)["QueueUrl"]
    message = {
        "order_id": order["order_id"],
        "user_id": order["user_id"],
        "total": str(order["total"]),
        "created_at": order["created_at"],
    }
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message, ensure_ascii=False))
    return _json_value(order)


def list_orders() -> list[dict]:
    paginator = dynamodb.meta.client.get_paginator("scan")
    items = []
    for page in paginator.paginate(TableName=ORDERS_TABLE):
        items.extend(page.get("Items", []))
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return _json_value(items)


def upload_user_image(user_id: str, file_obj: BinaryIO, filename: str, content_type: str) -> dict:
    safe_name = os.path.basename(filename).replace(" ", "-")
    key = f"users/{user_id}/{uuid.uuid4()}-{safe_name}"
    s3.upload_fileobj(
        file_obj,
        USER_IMAGES_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type or "application/octet-stream"},
    )
    return {"bucket": USER_IMAGES_BUCKET, "key": key, "user_id": user_id}


def queue_status() -> dict:
    queue_url = sqs.get_queue_url(QueueName=ORDERS_QUEUE)["QueueUrl"]
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
    )["Attributes"]
    return {"queue_url": queue_url, **attrs}


def service_status() -> dict:
    return {
        "endpoint": AWS_ENDPOINT_URL,
        "products": len(list_products()),
        "orders": len(list_orders()),
        "queue": queue_status(),
        "bucket": USER_IMAGES_BUCKET,
    }
