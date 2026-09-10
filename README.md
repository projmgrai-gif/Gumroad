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
python3 gumroad_cli.py page-set <product_id> <html_path>           # replace the product page with custom HTML
python3 gumroad_cli.py page-clear <product_id>                     # remove the custom page (restore default)
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

## Notes on undocumented behavior

`product-create`, `file-upload`, `thumbnail-set`, and `page-set`/`page-clear` rely on
endpoints not covered in Gumroad's public API docs, found by probing the API's own
error messages against a live account:

- File uploads use a presign → S3 multipart PUT → complete flow
  (`POST /files/presign`, `PUT` to the returned S3 URL, `POST /files/complete`),
  then attach via `PUT /products/:id` with `files[][url]`.
- Thumbnails use Rails ActiveStorage direct uploads
  (`POST /direct_uploads` with a `blob` descriptor, `PUT` to the returned S3 URL,
  then `POST /products/:id/thumbnail` with `signed_blob_id`).
- A custom landing page is just the product's `custom_html` field via
  `PUT /products/:id`. The response includes a `sanitization_report` (what the
  server stripped) and, if the page has no buy element, a `warning`. Setting
  `custom_html` to an empty string clears it and restores the default page.
  At time of writing, embedding an `<img>` tag with a `data:` URI (or a CSS
  `background-image: url(data:...)`) intermittently fails server-side review —
  use the product's own hosted asset URLs (`public-files.gumroad.com`, from
  `product get`) or inline SVG instead.
