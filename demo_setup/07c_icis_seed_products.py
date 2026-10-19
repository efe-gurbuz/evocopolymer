"""
07c_icis_seed_products.py
Seed x_icis_url / x_icis_ref_price / x_icis_price_date on the 27 Areks
raw-material products (reference price fluctuating within +/-5% of cost).

Split out from 07b as a standalone script: running the data seed in the
same process/transaction as the base.automation + ir.actions.server
creation caused the writes to silently not persist (likely due to a
registry reload triggered by the automation rule creation disrupting
the live env mid-script) - verified by reproducing a single-product
write in isolation (worked) vs. inside the combined script (didn't).
Running this as its own process avoids the issue entirely.

Idempotent.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/07c_icis_seed_products.py
"""

import datetime
import hashlib

print("=" * 70)
print("07c_icis_seed_products.py starting")
print("=" * 70)

Product = env['product.template'].sudo()
ICIS_URL = "https://www.icis.com/explore/commodities/chemicals/polyurethanes/"
USD_TO_TRY = 34.50
today = datetime.date.today()

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
assert areks

hammadde_categs = env['product.category'].sudo().search(
    [('name', 'in', ['Polioller', 'İzosiyanatlar', 'Yardımcı Kimyasallar'])])
raw_materials = Product.search([('categ_id', 'in', hammadde_categs.ids)])
print(f"  found {len(raw_materials)} raw-material products")

updated = 0
for prod in raw_materials:
    # NOTE (bug found & fixed): a bare prod.standard_price reads against
    # env.company, which is not guaranteed to be Areks - scope explicitly.
    cost_usd = round((prod.with_company(areks).standard_price or 0.0) / USD_TO_TRY, 4)
    h = int(hashlib.md5(prod.name.encode('utf-8')).hexdigest(), 16)
    pct = ((h % 1001) / 1000.0) * 0.10 - 0.05  # deterministic +/-5%
    ref_price = round(cost_usd * (1 + pct), 4)
    vals = {}
    if prod.x_icis_url != ICIS_URL:
        vals['x_icis_url'] = ICIS_URL
    if abs((prod.x_icis_ref_price or 0.0) - ref_price) > 1e-6:
        vals['x_icis_ref_price'] = ref_price
    if prod.x_icis_price_date != today:
        vals['x_icis_price_date'] = today
    if vals:
        prod.write(vals)
        env.cr.commit()
        updated += 1
        print(f"  [OK] {prod.name}: ref_price={ref_price} USD/kg")
    else:
        print(f"  [SKIP] {prod.name}: already up to date")

print("-" * 70)
print(f"SUMMARY: updated={updated} skipped={len(raw_materials) - updated}")

# verify by re-reading from a fresh browse (bypass local cache)
check = Product.browse(raw_materials[:3].ids)
check.invalidate_recordset()
for p in check:
    print(f"   VERIFY {p.name}: url_set={bool(p.x_icis_url)} ref_price={p.x_icis_ref_price} date={p.x_icis_price_date}")

print("=" * 70)
print("07c_icis_seed_products.py done")
print("=" * 70)
