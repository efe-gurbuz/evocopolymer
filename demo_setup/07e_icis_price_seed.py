"""
07e_icis_price_seed.py
ICIS PLAN B demo data: one x_icis_price record per raw material per
month for the last 6 months (price within +/-5% of cost, in USD).

Standalone script (kept separate from model/view/menu creation - see
07d/07c notes on registry-reload interference when mixed with data
writes in the same process).

Idempotent: search by (x_product_id, x_date) before create.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/07e_icis_price_seed.py
"""

import datetime
import hashlib

print("=" * 70)
print("07e_icis_price_seed.py starting")
print("=" * 70)

Product = env['product.template'].sudo()
# NOTE (bug found & fixed): x_icis_price is a custom/manual model whose
# active flag is named x_active (see 00d_remap_and_archive_old.py notes -
# Odoo's _active_name resolution only recognizes 'active'/'x_active' for
# manual models). A new row created WITHOUT x_active explicitly set gets
# NULL, which the default active_test filter excludes just like False -
# so every create() below must set x_active=True explicitly, and any
# pre-existing NULL rows (from a run before this fix existed) must be
# healed the same way.
IcisPrice = env['x_icis_price'].sudo().with_context(active_test=False)
USD = env['res.currency'].sudo().search([('name', '=', 'USD')], limit=1)
USD_TO_TRY = 34.50
assert USD

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
assert areks

hammadde_categs = env['product.category'].sudo().search(
    [('name', 'in', ['Polioller', 'İzosiyanatlar', 'Yardımcı Kimyasallar'])])
raw_materials = Product.search([('categ_id', 'in', hammadde_categs.ids)])
print(f"  found {len(raw_materials)} raw-material products")

today = datetime.date.today()
# first day of the current month, then 5 more going back = 6 months total
month_starts = []
y, m = today.year, today.month
for i in range(6):
    mm = m - i
    yy = y
    while mm <= 0:
        mm += 12
        yy -= 1
    month_starts.append(datetime.date(yy, mm, 1))
month_starts.reverse()  # oldest first

created = 0
skipped = 0
healed = 0
for prod in raw_materials:
    # NOTE (bug found & fixed): scope explicitly to Areks's own cost.
    cost_usd = round((prod.with_company(areks).standard_price or 0.0) / USD_TO_TRY, 4)
    for month_date in month_starts:
        existing = IcisPrice.search([
            ('x_product_id', '=', prod.id),
            ('x_date', '=', month_date),
        ], limit=1)
        if existing:
            if not existing.x_active:
                existing.x_active = True
                healed += 1
            skipped += 1
            continue
        key = f"{prod.name}-{month_date.isoformat()}"
        h = int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16)
        pct = ((h % 1001) / 1000.0) * 0.10 - 0.05  # +/-5%
        price = round(cost_usd * (1 + pct), 4)
        IcisPrice.create({
            'x_name': f"{prod.name} - {month_date.strftime('%Y-%m')}",
            'x_product_id': prod.id,
            'x_date': month_date,
            'x_price': price,
            'x_currency_id': USD.id,
            'x_active': True,
        })
        created += 1

env.cr.commit()

print("-" * 70)
print(f"SUMMARY: created={created} skipped(existing)={skipped} healed(x_active fix)={healed} "
      f"total_expected={len(raw_materials) * 6}")
total_default = env['x_icis_price'].sudo().search_count([])
total_all = IcisPrice.search_count([])
print(f"  total x_icis_price records visible by default: {total_default} (with active_test=False: {total_all})")
print("=" * 70)
print("07e_icis_price_seed.py done")
print("=" * 70)
