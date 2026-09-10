# Gumroad

A small Python command-line client for the [Gumroad API (v2)](https://help.gumroad.com/article/280-gumroad-api).

## Setup

```bash
pip install -r requirements.txt
export GUMROAD_ACCESS_TOKEN=your_access_token_here
```

Get an access token from your Gumroad account under **Settings → Advanced → Applications**.
Never commit your token — it's read from the `GUMROAD_ACCESS_TOKEN` environment
variable (or passed per-command with `--token`).

## Usage

```bash
python3 gumroad_cli.py user
python3 gumroad_cli.py products
python3 gumroad_cli.py product <product_id> [--action get|enable|disable]
python3 gumroad_cli.py product-create <name> <price_cents> [--description TEXT] [--publish]
python3 gumroad_cli.py product-update <product_id> [--name NAME] [--description TEXT] [--price-cents N] [--tag TAG ...]
python3 gumroad_cli.py product-delete <product_id>
python3 gumroad_cli.py file-upload <product_id> <local_path>       # attach a downloadable file
python3 gumroad_cli.py thumbnail-set <product_id> <local_path>     # set the product's cover thumbnail
python3 gumroad_cli.py sales [--after DATE] [--before DATE] [--email EMAIL] [--product-id ID]
python3 gumroad_cli.py sale <sale_id>
python3 gumroad_cli.py subscribers <product_id> [--email EMAIL]
python3 gumroad_cli.py license-verify <product_permalink> <license_key> [--no-increment]
python3 gumroad_cli.py license-enable <product_permalink> <license_key>
python3 gumroad_cli.py license-disable <product_permalink> <license_key>
python3 gumroad_cli.py offer-codes <product_id>
python3 gumroad_cli.py offer-code-create <product_id> <name> <amount_off> [--type cents|percent] [--max-purchase-count N] [--universal]
```

Every command prints the raw JSON response from the Gumroad API.
