"""
10a_purchases.py
Areks historical purchasing: 18 confirmed + received POs over the last
6 months, across the 4 chemical vendors (different currencies), each
line carrying an ICIS comparison price (variance -4%..+7%), 3 of the
POs with a landed cost applied, and a posted vendor bill for each PO.

Idempotent: tagged via a unique `origin` marker per PO index; re-running
skips POs whose marker already exists.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/10a_purchases.py
"""

import datetime
import hashlib

print("=" * 70)
print("10a_purchases.py starting")
print("=" * 70)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
Product = env['product.template'].sudo()
Partner = env['res.partner'].sudo()
PO = env['purchase.order'].sudo().with_company(areks)
Lot = env['stock.lot'].sudo()
LandedCost = env['stock.landed.cost'].sudo().with_company(areks)
AccountMove = env['account.move'].sudo()

VENDORS = {
    'nordpol': Partner.search([('name', '=', 'Nordpol Chemie GmbH')], limit=1),
    'gulfstream': Partner.search([('name', '=', 'Gulfstream Petrochem FZE')], limit=1),
    'eastbridge': Partner.search([('name', '=', 'Eastbridge Isocyanates Ltd.')], limit=1),
    'anatolia': Partner.search([('name', '=', 'Anatolia Specialty Chemicals A.Ş.')], limit=1),
}
navlun = Product.search([('name', '=', 'Navlun')], limit=1)
gumruk_vergisi = Product.search([('name', '=', 'Gümrük Vergisi')], limit=1)
gumruk_musavirlik = Product.search([('name', '=', 'Gümrük Müşavirlik Hizmeti')], limit=1)
marmara_gumruk = Partner.search([('name', '=', 'Marmara Gümrük Müşavirliği')], limit=1)
bogazici_lojistik = Partner.search([('name', '=', 'Boğaziçi Lojistik')], limit=1)

USD_TO_TRY = 34.50
EUR_TO_TRY = 37.20
today = datetime.date.today()

# 18 POs: rotate vendors, spread dates over last ~170 days
PO_PLAN = []
vendor_keys = list(VENDORS.keys())
for i in range(18):
    vendor_key = vendor_keys[i % len(vendor_keys)]
    days_ago = 170 - i * 9  # spread across ~6 months, newest last
    PO_PLAN.append((i, vendor_key, max(days_ago, 3)))

LANDED_COST_INDICES = {2, 7, 12}  # 3 of the 18


def icis_price_in_currency(product, currency):
    icis_usd = product.x_icis_ref_price or 0.0
    if currency.name == 'USD':
        return icis_usd
    if currency.name == 'EUR':
        return round(icis_usd * USD_TO_TRY / EUR_TO_TRY, 4)
    return round(icis_usd * USD_TO_TRY, 4)  # TRY


created_pos = 0
skipped_pos = 0

for idx, vendor_key, days_ago in PO_PLAN:
    marker = f"AREKS-HIST-PO-{idx:02d}"
    vendor = VENDORS[vendor_key]
    # audit-rebuild fix: a marker match alone can hit a leftover PO
    # still sitting under the OLD (now archived/renamed) company id -
    # company_id must always be part of the idempotency check too.
    existing = PO.search([('partner_ref', '=', marker), ('company_id', '=', areks.id)], limit=1)
    if existing:
        skipped_pos += 1
        print(f"  [SKIP] PO #{idx} already exists ({existing.name})")
        continue

    backdate = today - datetime.timedelta(days=days_ago)
    products = env['product.supplierinfo'].sudo().search(
        [('partner_id', '=', vendor.id)]).mapped('product_tmpl_id')
    if not products:
        print(f"  [WARN] vendor {vendor.name} has no products, skipping #{idx}")
        continue
    h = int(hashlib.md5(marker.encode('utf-8')).hexdigest(), 16)
    n_lines = 1 + (h % min(3, len(products)))
    chosen_products = list(products)[:n_lines] if len(products) <= n_lines else \
        sorted(products, key=lambda p: (h + p.id) % 97)[:n_lines]

    order_lines = []
    for p in chosen_products:
        h2 = int(hashlib.md5(f"{marker}-{p.name}".encode('utf-8')).hexdigest(), 16)
        qty = 500 + (h2 % 20) * 100  # 500..2400 kg
        currency = vendor.property_purchase_currency_id
        icis_price = icis_price_in_currency(p, currency)
        variance = -0.04 + ((h2 % 1001) / 1000.0) * 0.11  # [-4%, +7%]
        price_unit = round(icis_price * (1 + variance), 4) if icis_price else 0.0
        order_lines.append((0, 0, {
            'product_id': p.product_variant_id.id,
            'product_qty': qty,
            'price_unit': price_unit,
            'x_icis_price': icis_price,
            'date_planned': backdate,
        }))

    po = PO.create({
        'partner_id': vendor.id,
        'company_id': areks.id,
        # NOTE (bug found & fixed): purchase.order.currency_id only
        # defaults to the vendor's currency via an ONCHANGE on
        # partner_id - a raw ORM create() never fires onchanges, so it
        # silently fell back to the plain field default (company
        # currency, TRY) regardless of vendor, while price_unit was
        # still computed in the VENDOR's currency (icis_price_in_currency)
        # - understating EUR/USD vendor bills by the TRY exchange factor.
        # Must be set explicitly.
        'currency_id': vendor.property_purchase_currency_id.id,
        'date_order': backdate,
        'partner_ref': marker,
        'order_line': order_lines,
    })
    po.button_confirm()
    if po.state == 'to approve':
        po.button_approve()
    po.date_approve = backdate

    picking = po.picking_ids[:1]
    if picking:
        picking.move_ids.picked = True
        for move in picking.move_ids:
            lot = Lot.create({
                # "ARK-" prefix (not "LOT-") to avoid colliding with
                # orphaned zero-qty lots left over from the first
                # (currency-bug) attempt at this data, which could not
                # be deleted (FK from their now-empty stock.quant rows).
                # audit point 1: never set company_id on a lot - shared
                # products (company_id=False) naturally compute a shared
                # (company_id=False) lot.
                'name': f"ARK-{move.product_id.default_code or move.product_id.name[:8]}-{idx:02d}",
                'product_id': move.product_id.id,
            })
            for ml in move.move_line_ids:
                ml.lot_id = lot.id
                ml.quantity = move.product_uom_qty
        picking.move_ids.write({'date': backdate})
        picking.button_validate()

    # landed cost on selected POs
    if idx in LANDED_COST_INDICES and picking:
        lc = LandedCost.create({
            'picking_ids': [(6, 0, picking.ids)],
            'company_id': areks.id,
            'date': backdate,
            'cost_lines': [
                (0, 0, {'product_id': navlun.product_variant_id.id, 'price_unit': 2500.0, 'split_method': 'by_weight'}),
                (0, 0, {'product_id': gumruk_vergisi.product_variant_id.id, 'price_unit': 4000.0, 'split_method': 'by_current_cost_price'}),
            ],
        })
        try:
            lc.compute_landed_cost()
            lc.button_validate()
            print(f"    [OK] landed cost applied on PO #{idx} ({lc.state})")
        except Exception as e:
            print(f"    [WARN] landed cost failed on PO #{idx}: {e}")

    # vendor bill
    try:
        action = po.action_create_invoice()
        bill = AccountMove.browse(action['res_id'])
        bill.invoice_date = backdate
        bill.action_post()
        bill_state = bill.state
    except Exception as e:
        bill_state = f"ERROR: {e}"

    env.cr.commit()
    created_pos += 1
    print(f"  [OK] PO #{idx} {po.name} vendor={vendor.name} date={backdate} "
          f"total={po.amount_total} {po.currency_id.name} bill={bill_state}")

print("-" * 70)
print(f"SUMMARY: created={created_pos} skipped(existing)={skipped_pos}")
print("=" * 70)
print("10a_purchases.py done")
print("=" * 70)
