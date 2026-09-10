#!/usr/bin/env python3
"""Command-line client for the Gumroad API (v2).

Reads the access token from the GUMROAD_ACCESS_TOKEN environment variable
(or --token), never from a committed file. See README.md for setup and
the full list of commands.
"""
from __future__ import annotations

import argparse
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
