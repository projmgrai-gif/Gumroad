#!/usr/bin/env python3
"""Command-line client for the Gumroad API (v2).

Reads the access token from the GUMROAD_ACCESS_TOKEN environment variable
(or --token), never from a committed file. See README.md for setup and
the full list of commands.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from typing import Any

import requests

API_BASE = "https://api.gumroad.com/v2"


class GumroadError(RuntimeError):
    pass


class GumroadClient:
    def __init__(self, token: str):
        if not token:
            raise GumroadError(
                "No access token provided. Set GUMROAD_ACCESS_TOKEN or pass --token."
            )
        self.token = token
        self.session = requests.Session()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        params = kwargs.pop("params", {}) or {}
        data = kwargs.pop("data", {}) or {}
        if method.upper() == "GET":
            params["access_token"] = self.token
        elif isinstance(data, list):
            data.append(("access_token", self.token))
        else:
            data["access_token"] = self.token

        resp = self.session.request(
            method, f"{API_BASE}{path}", params=params, data=data, **kwargs
        )
        try:
            payload = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise GumroadError(f"Non-JSON response from {path}")

        if not resp.ok or not payload.get("success", True):
            message = payload.get("message", resp.text)
            raise GumroadError(f"{method} {path} failed: {message}")
        return payload

    # -- User -----------------------------------------------------------
    def get_user(self) -> dict:
        return self._request("GET", "/user")

    # -- Products ---------------------------------------------------------
    def list_products(self) -> dict:
        return self._request("GET", "/products")

    def get_product(self, product_id: str) -> dict:
        return self._request("GET", f"/products/{product_id}")

    def enable_product(self, product_id: str) -> dict:
        return self._request("PUT", f"/products/{product_id}/enable")

    def disable_product(self, product_id: str) -> dict:
        return self._request("PUT", f"/products/{product_id}/disable")

    def create_product(self, name: str, price_cents: int, description: str | None = None,
                        published: bool = False) -> dict:
        data = {"name": name, "price": price_cents, "published": str(published).lower()}
        if description is not None:
            data["description"] = description
        return self._request("POST", "/products", data=data)

    def update_product(self, product_id: str, **fields: Any) -> dict:
        data: list[tuple[str, Any]] = []
        for key, value in fields.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        data.extend((f"{key}[][{subkey}]", subvalue) for subkey, subvalue in item.items())
                    else:
                        data.append((f"{key}[]", item))
            else:
                data.append((key, value))
        return self._request("PUT", f"/products/{product_id}", data=data)

    def delete_product(self, product_id: str) -> dict:
        return self._request("DELETE", f"/products/{product_id}")

    def upload_file(self, local_path: str, filename: str | None = None) -> str:
        """Upload a local file (e.g. a product's downloadable content) to Gumroad's
        storage via the presign -> S3 PUT -> complete flow, returning its file_url.
        Attach it to a product afterwards with update_product(files=[url])."""
        filename = filename or os.path.basename(local_path)
        size = os.path.getsize(local_path)
        presign = self._request(
            "POST", "/files/presign", data={"filename": filename, "file_size": size}
        )
        with open(local_path, "rb") as fh:
            content = fh.read()
        part = presign["parts"][0]
        put_resp = self.session.put(part["presigned_url"], data=content)
        put_resp.raise_for_status()
        etag = put_resp.headers["ETag"].strip('"')

        complete_data = [
            ("upload_id", presign["upload_id"]),
            ("key", presign["key"]),
            ("parts[][part_number]", part["part_number"]),
            ("parts[][etag]", etag),
        ]
        result = self._request("POST", "/files/complete", data=complete_data)
        return result["file_url"]

    def set_thumbnail(self, product_id: str, local_path: str, filename: str | None = None) -> dict:
        """Upload a local image and set it as a product's cover thumbnail via
        Gumroad's direct-upload (ActiveStorage) flow."""
        filename = filename or os.path.basename(local_path)
        with open(local_path, "rb") as fh:
            content = fh.read()
        checksum = base64.b64encode(hashlib.md5(content).digest()).decode()
        content_type = "image/png" if filename.lower().endswith(".png") else "image/jpeg"

        resp = self.session.post(
            f"{API_BASE}/direct_uploads",
            params={"access_token": self.token},
            json={"blob": {
                "filename": filename,
                "content_type": content_type,
                "byte_size": len(content),
                "checksum": checksum,
            }},
        )
        resp.raise_for_status()
        direct_upload = resp.json()

        upload = direct_upload["direct_upload"]
        put_resp = self.session.put(upload["url"], data=content, headers=upload["headers"])
        put_resp.raise_for_status()

        result = self._request(
            "POST",
            f"/products/{product_id}/thumbnail",
            data={"signed_blob_id": direct_upload["signed_id"]},
        )
        return result["thumbnail"]

    # -- Sales ------------------------------------------------------------
    def list_sales(self, after: str | None = None, before: str | None = None,
                    page_key: str | None = None, email: str | None = None,
                    product_id: str | None = None) -> dict:
        params = {}
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if page_key:
            params["page_key"] = page_key
        if email:
            params["email"] = email
        if product_id:
            params["product_id"] = product_id
        return self._request("GET", "/sales", params=params)

    def get_sale(self, sale_id: str) -> dict:
        return self._request("GET", f"/sales/{sale_id}")

    # -- Subscribers --------------------------------------------------------
    def list_subscribers(self, product_id: str, email: str | None = None) -> dict:
        params = {"email": email} if email else {}
        return self._request("GET", f"/products/{product_id}/subscribers", params=params)

    # -- Licenses ---------------------------------------------------------
    def verify_license(self, product_permalink: str, license_key: str,
                        increment_uses_count: bool = True) -> dict:
        return self._request(
            "POST",
            "/licenses/verify",
            data={
                "product_permalink": product_permalink,
                "license_key": license_key,
                "increment_uses_count": str(increment_uses_count).lower(),
            },
        )

    def enable_license(self, product_permalink: str, license_key: str) -> dict:
        return self._request(
            "PUT",
            "/licenses/enable",
            data={"product_permalink": product_permalink, "license_key": license_key},
        )

    def disable_license(self, product_permalink: str, license_key: str) -> dict:
        return self._request(
            "PUT",
            "/licenses/disable",
            data={"product_permalink": product_permalink, "license_key": license_key},
        )

    # -- Offer codes --------------------------------------------------------
    def list_offer_codes(self, product_id: str) -> dict:
        return self._request("GET", f"/products/{product_id}/offer_codes")

    def create_offer_code(self, product_id: str, name: str, amount_off: str,
                           offer_type: str = "cents", max_purchase_count: str | None = None,
                           universal: bool = False) -> dict:
        data = {
            "name": name,
            "amount_off": amount_off,
            "offer_type": offer_type,
            "universal": str(universal).lower(),
        }
        if max_purchase_count is not None:
            data["max_purchase_count"] = max_purchase_count
        return self._request("POST", f"/products/{product_id}/offer_codes", data=data)


def _print(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gumroad API v2 command-line client")
    parser.add_argument(
        "--token",
        default=os.environ.get("GUMROAD_ACCESS_TOKEN"),
        help="Gumroad access token (defaults to GUMROAD_ACCESS_TOKEN env var)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("user", help="Show the authenticated user's account info")

    products = sub.add_parser("products", help="List all products")
    products.set_defaults(action="list")

    product = sub.add_parser("product", help="Get / enable / disable a product")
    product.add_argument("product_id")
    product.add_argument(
        "--action", choices=["get", "enable", "disable"], default="get"
    )

    product_create = sub.add_parser("product-create", help="Create a new product")
    product_create.add_argument("name")
    product_create.add_argument("price_cents", type=int, help="Price in cents, e.g. 1799 for $17.99")
    product_create.add_argument("--description")
    product_create.add_argument(
        "--publish", action="store_true", help="Publish immediately (default: create as draft)"
    )

    product_update = sub.add_parser(
        "product-update", help="Update a product's name/description/price/tags"
    )
    product_update.add_argument("product_id")
    product_update.add_argument("--name")
    product_update.add_argument("--description")
    product_update.add_argument("--price-cents", type=int)
    product_update.add_argument("--tag", dest="tags", action="append", help="Repeatable")

    product_delete = sub.add_parser("product-delete", help="Delete a product")
    product_delete.add_argument("product_id")

    file_upload = sub.add_parser(
        "file-upload", help="Upload a local file and attach it to a product's downloadable content"
    )
    file_upload.add_argument("product_id")
    file_upload.add_argument("local_path")

    thumbnail_set = sub.add_parser(
        "thumbnail-set", help="Upload a local image and set it as a product's thumbnail"
    )
    thumbnail_set.add_argument("product_id")
    thumbnail_set.add_argument("local_path")

    sales = sub.add_parser("sales", help="List sales")
    sales.add_argument("--after")
    sales.add_argument("--before")
    sales.add_argument("--page-key")
    sales.add_argument("--email")
    sales.add_argument("--product-id")

    sale = sub.add_parser("sale", help="Get a single sale by id")
    sale.add_argument("sale_id")

    subscribers = sub.add_parser("subscribers", help="List subscribers for a product")
    subscribers.add_argument("product_id")
    subscribers.add_argument("--email")

    license_verify = sub.add_parser("license-verify", help="Verify a license key")
    license_verify.add_argument("product_permalink")
    license_verify.add_argument("license_key")
    license_verify.add_argument(
        "--no-increment", action="store_true", help="Do not increment the uses count"
    )

    license_enable = sub.add_parser("license-enable", help="Enable a license key")
    license_enable.add_argument("product_permalink")
    license_enable.add_argument("license_key")

    license_disable = sub.add_parser("license-disable", help="Disable a license key")
    license_disable.add_argument("product_permalink")
    license_disable.add_argument("license_key")

    offer_codes = sub.add_parser("offer-codes", help="List offer codes for a product")
    offer_codes.add_argument("product_id")

    offer_code_create = sub.add_parser("offer-code-create", help="Create an offer code")
    offer_code_create.add_argument("product_id")
    offer_code_create.add_argument("name")
    offer_code_create.add_argument("amount_off")
    offer_code_create.add_argument("--type", choices=["cents", "percent"], default="cents")
    offer_code_create.add_argument("--max-purchase-count")
    offer_code_create.add_argument("--universal", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        client = GumroadClient(args.token)

        if args.command == "user":
            _print(client.get_user())
        elif args.command == "products":
            _print(client.list_products())
        elif args.command == "product":
            if args.action == "get":
                _print(client.get_product(args.product_id))
            elif args.action == "enable":
                _print(client.enable_product(args.product_id))
            elif args.action == "disable":
                _print(client.disable_product(args.product_id))
        elif args.command == "product-create":
            _print(
                client.create_product(
                    args.name, args.price_cents, description=args.description,
                    published=args.publish,
                )
            )
        elif args.command == "product-update":
            fields: dict[str, Any] = {}
            if args.name is not None:
                fields["name"] = args.name
            if args.description is not None:
                fields["description"] = args.description
            if args.price_cents is not None:
                fields["price"] = args.price_cents
            if args.tags:
                fields["tags"] = args.tags
            _print(client.update_product(args.product_id, **fields))
        elif args.command == "product-delete":
            _print(client.delete_product(args.product_id))
        elif args.command == "file-upload":
            file_url = client.upload_file(args.local_path)
            _print(client.update_product(args.product_id, files=[{"url": file_url}]))
        elif args.command == "thumbnail-set":
            _print(client.set_thumbnail(args.product_id, args.local_path))
        elif args.command == "sales":
            _print(
                client.list_sales(
                    after=args.after,
                    before=args.before,
                    page_key=args.page_key,
                    email=args.email,
                    product_id=args.product_id,
                )
            )
        elif args.command == "sale":
            _print(client.get_sale(args.sale_id))
        elif args.command == "subscribers":
            _print(client.list_subscribers(args.product_id, email=args.email))
        elif args.command == "license-verify":
            _print(
                client.verify_license(
                    args.product_permalink,
                    args.license_key,
                    increment_uses_count=not args.no_increment,
                )
            )
        elif args.command == "license-enable":
            _print(client.enable_license(args.product_permalink, args.license_key))
        elif args.command == "license-disable":
            _print(client.disable_license(args.product_permalink, args.license_key))
        elif args.command == "offer-codes":
            _print(client.list_offer_codes(args.product_id))
        elif args.command == "offer-code-create":
            _print(
                client.create_offer_code(
                    args.product_id,
                    args.name,
                    args.amount_off,
                    offer_type=args.type,
                    max_purchase_count=args.max_purchase_count,
                    universal=args.universal,
                )
            )
    except GumroadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
