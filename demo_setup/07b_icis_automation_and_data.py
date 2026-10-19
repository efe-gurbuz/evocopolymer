"""
07b_icis_automation_and_data.py
ICIS PLAN A continued:
- base.automation rule computing purchase.order.line.x_icis_variance_pct
  (since Studio-style custom fields can't carry real @api.depends code,
  the standard no-code equivalent is an Automation Rule + Server Action).
- Seed x_icis_url / x_icis_ref_price / x_icis_price_date on all 27 Areks
  raw-material products, reference price fluctuating within +/-5% of cost.

Idempotent.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/07b_icis_automation_and_data.py
"""

import datetime
import hashlib

print("=" * 70)
print("07b_icis_automation_and_data.py starting")
print("=" * 70)

Automation = env['base.automation'].sudo()
ServerAction = env['ir.actions.server'].sudo()
Product = env['product.template'].sudo()
IMF = env['ir.model.fields'].sudo()

# -----------------------------------------------------------------------
# Automation rule: compute x_icis_variance_pct on purchase.order.line
# -----------------------------------------------------------------------
rule_name = "ICIS Sapma % Hesapla"
rule = Automation.search([('name', '=', rule_name)], limit=1)
if not rule:
    pol_model = env['ir.model'].sudo().search([('model', '=', 'purchase.order.line')], limit=1)
    price_unit_f = IMF.search([('model', '=', 'purchase.order.line'), ('name', '=', 'price_unit')], limit=1)
    icis_price_f = IMF.search([('model', '=', 'purchase.order.line'), ('name', '=', 'x_icis_price')], limit=1)
    rule = Automation.create({
        'name': rule_name,
        'model_id': pol_model.id,
        'trigger': 'on_create_or_write',
        'trigger_field_ids': [(6, 0, (price_unit_f | icis_price_f).ids)],
        'action_server_ids': [(0, 0, {
            'name': rule_name,
            'model_id': pol_model.id,
            'state': 'code',
            'code': (
                "for record in records:\n"
                "    if record.x_icis_price:\n"
                "        pct = (record.price_unit - record.x_icis_price) / record.x_icis_price * 100.0\n"
                "    else:\n"
                "        pct = 0.0\n"
                "    record.write({'x_icis_variance_pct': pct})\n"
            ),
        })],
    })
    print(f"  [OK] automation rule created: {rule_name} (id={rule.id})")
else:
    print(f"  [SKIP] automation rule exists: {rule_name} (id={rule.id})")

env.cr.commit()

# -----------------------------------------------------------------------
# audit point 12: ALSO update x_icis_variance_pct live/instantly via
# on_change (not only on save). base.automation's genuine trigger='on_change'
# registers a real Odoo onchange method (on_change_field_ids), fired in
# the UI the instant price_unit/x_icis_price are edited, before any save.
# The underlying server action code executes sandboxed (safe_eval) just
# like the on_create_or_write one above, so direct attribute assignment
# (record.field = value) is still forbidden (STORE_ATTR) - but unlike
# write()/update(), an onchange server action is expected to return its
# changes via a plain `action = {'value': {...}}` dict (read back by
# base_automation's onchange wrapper and applied with self.update()).
# -----------------------------------------------------------------------
onchange_rule_name = "ICIS Sapma % Hesapla (Canlı/Onchange)"
onchange_rule = Automation.search([('name', '=', onchange_rule_name)], limit=1)
if not onchange_rule:
    pol_model = env['ir.model'].sudo().search([('model', '=', 'purchase.order.line')], limit=1)
    price_unit_f = IMF.search([('model', '=', 'purchase.order.line'), ('name', '=', 'price_unit')], limit=1)
    icis_price_f = IMF.search([('model', '=', 'purchase.order.line'), ('name', '=', 'x_icis_price')], limit=1)
    onchange_rule = Automation.create({
        'name': onchange_rule_name,
        'model_id': pol_model.id,
        'trigger': 'on_change',
        'on_change_field_ids': [(6, 0, (price_unit_f | icis_price_f).ids)],
        'action_server_ids': [(0, 0, {
            'name': onchange_rule_name,
            'model_id': pol_model.id,
            'state': 'code',
            'code': (
                "if record.x_icis_price:\n"
                "    pct = (record.price_unit - record.x_icis_price) / record.x_icis_price * 100.0\n"
                "else:\n"
                "    pct = 0.0\n"
                "action = {'value': {'x_icis_variance_pct': pct}}\n"
            ),
        })],
    })
    print(f"  [OK] onchange automation rule created: {onchange_rule_name} (id={onchange_rule.id})")
else:
    print(f"  [SKIP] onchange automation rule exists: {onchange_rule_name} (id={onchange_rule.id})")

env.cr.commit()

# -----------------------------------------------------------------------
# Seed ICIS reference data on the 27 Areks raw materials
# -----------------------------------------------------------------------
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
    # NOTE (bug found & fixed, same root cause as audit point 2): a bare
    # prod.standard_price read resolves against env.company, which for
    # an odoo-bin shell session is NOT guaranteed to be Areks/Evoco (it
    # silently fell back to an archived company here, reading 0.0 for
    # every single product) - these raw materials are costed from
    # Areks's purchasing side, so scope explicitly via with_company(areks).
    cost_usd = round((prod.with_company(areks).standard_price or 0.0) / USD_TO_TRY, 4)
    # deterministic +/-5% variance seeded from the product name (stable across re-runs)
    h = int(hashlib.md5(prod.name.encode('utf-8')).hexdigest(), 16)
    pct = ((h % 1001) / 1000.0) * 0.10 - 0.05  # range [-0.05, +0.05]
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
        updated += 1

env.cr.commit()
print(f"  [OK] ICIS reference data set/refreshed on {updated} products ({len(raw_materials) - updated} already up to date)")

print("-" * 70)
sample = raw_materials[:3]
for p in sample:
    print(f"   {p.name}: url set={bool(p.x_icis_url)} ref_price={p.x_icis_ref_price} date={p.x_icis_price_date}")
print("=" * 70)
print("07b_icis_automation_and_data.py done")
print("=" * 70)
