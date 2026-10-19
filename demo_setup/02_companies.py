"""
02_companies.py
Set up the two Areks Group root companies (Areks Kimya, Evoco Polimer),
their currencies, Turkish chart of accounts, warehouses, PO double
validation threshold, and inter-company sale/purchase sync settings.

Idempotent: safe to run multiple times (search-before-create everywhere).

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/02_companies.py
"""

print("=" * 70)
print("02_companies.py starting")
print("=" * 70)

Company = env['res.company'].sudo()
Currency = env['res.currency'].sudo().with_context(active_test=False)
Country = env['res.country'].sudo()
State = env['res.country.state'].sudo()
Warehouse = env['stock.warehouse'].sudo()
Rate = env['res.currency.rate'].sudo()

TR = Country.search([('code', '=', 'TR')], limit=1)
assert TR, "Turkey country not found in res.country"

istanbul = State.search([('country_id', '=', TR.id), ('name', 'ilike', 'stanbul')], limit=1)
kocaeli = State.search([('country_id', '=', TR.id), ('name', 'ilike', 'kocaeli')], limit=1)
print(f"  country TR={TR.id}, state Istanbul={istanbul.id if istanbul else None}, state Kocaeli={kocaeli.id if kocaeli else None}")

# --- Currencies: activate TRY, EUR (USD already active by default) ---
TRY = Currency.search([('name', '=', 'TRY')], limit=1)
EUR = Currency.search([('name', '=', 'EUR')], limit=1)
USD = Currency.search([('name', '=', 'USD')], limit=1)
assert TRY and EUR and USD, "TRY/EUR/USD currency records must exist in res.currency"

for cur in (TRY, EUR, USD):
    if not cur.active:
        cur.active = True
        print(f"  [OK] activated currency {cur.name}")
    else:
        print(f"  [SKIP] currency {cur.name} already active")

env.cr.commit()

# --- Areks Kimya ---
# NOTE (rebuild, "new company" approach): the original legacy company
# ("YourCompany" renamed in-place) was archived to "ESKİ – ..." by a
# separate cleanup step BEFORE this script runs, specifically so that
# the real name below is free and this search-or-create (same pattern
# as Evoco) creates a genuinely FRESH company - sidestepping a whole
# class of base-demo-data artifacts that were scoped to that old
# company's exact id (stale 2010 currency.rate rows, a USD-currency
# default pricelist, SMS delivery confirmation left on) - none of which
# a brand new company inherits.
areks = Company.search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
areks_vals = {
    'name': 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.',
    'street': 'Kiram Sk., Ankara Cd. No:4',
    'street2': 'Pendik',
    'city': 'İstanbul',
    'zip': '34906',
    'country_id': TR.id,
    'state_id': istanbul.id if istanbul else False,
    'phone': '+90 216 378 64 51',
    'email': 'info@arekschemicals.com',
    'currency_id': TRY.id,
}
if not areks:
    areks = Company.create(areks_vals)
    print(f"  [OK] Areks company created: id={areks.id}")
else:
    areks.write(areks_vals)
    print(f"  [OK] Areks company updated: id={areks.id} name={areks.name}")
env.cr.commit()

# --- Evoco Polimer (create new root company, no parent/child link) ---
evoco = Company.search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
if not evoco:
    evoco = Company.create({
        'name': 'Evoco Polimer San. Tic. A.Ş.',
        'street': 'GOSB Kemal Nehrozoğlu Cd. No:507/9',
        'street2': 'Gebze',
        'city': 'Kocaeli',
        'country_id': TR.id,
        'state_id': kocaeli.id if kocaeli else False,
        'phone': '+90 262 678 88 30',
        'email': 'info@evocopolymers.com',
        'currency_id': TRY.id,
    })
    print(f"  [OK] Evoco company created: id={evoco.id}")
else:
    print(f"  [SKIP] Evoco company already exists: id={evoco.id}")
env.cr.commit()

assert not areks.parent_id and not evoco.parent_id, "Companies must NOT have a parent/child relationship"
assert areks.id != evoco.id

# --- Demo exchange rates ---
# NOTE: res.currency.rate.rate is a GLOBAL pivot-relative value (see
# odoo/addons/base/models/res_currency.py _get_rates/_compute_current_rate):
# the effective USD->TRY (etc.) ratio used by _convert() is
# (TRY pivot rate) / (USD pivot rate), not a directly-entered "1 USD = X TRY"
# number. Writing the `company_rate` inverse field was tried first and
# produced wrong cross-rates (verified via Currency._convert()), so we set
# the underlying `rate` field directly instead, with TRY pinned to 1.0 as
# the per-company self-reference.
# Also: _get_rates() looks up the latest rate strictly BEFORE the query
# date ('name' < date), so a rate dated *today* is NOT used for today's
# conversions - and more importantly, we generate 6-months-BACKDATED
# business documents (section 10), so the rate must predate that whole
# window too. We date these rows 2024-01-01 (well before any historical
# demo document) so they are effective for the full 6-month history AND
# today/the future.
# NOTE (bug found & fixed): company 21 (ex-"YourCompany") had LEFTOVER
# base-demo seed currency.rate rows dated 2010-01-01 for USD/TRY/EUR
# (from when it was a USD-based company). Those predate our 2024-01-01
# row too, so they were harmless once our row exists - but they were
# the ones silently used (via the "nearest rate before date" fallback)
# for all our backdated documents BEFORE this fix existed, producing
# wildly wrong currency conversions on 18 historical POs/bills. Deleting
# them here keeps the rate table clean and avoids any future ambiguity
# for dates before 2024.
import datetime
today = datetime.date.today()
early_date = datetime.date(2024, 1, 1)
rate_plan = [
    (TRY, 1.0),
    (USD, 1 / 34.50),
    (EUR, 1 / 37.20),
]
old_seed_rows = Rate.search([
    ('company_id', 'in', [areks.id, evoco.id]),
    ('currency_id', 'in', [TRY.id, USD.id, EUR.id]),
    ('name', '<', early_date),
])
if old_seed_rows:
    print(f"  [OK] deleting {len(old_seed_rows)} stale pre-2024 currency.rate rows "
          f"(leftover base demo seed data that would otherwise win the "
          f"'nearest rate before date' fallback for backdated documents)")
    old_seed_rows.unlink()

for company in (areks, evoco):
    for currency, pivot_rate in rate_plan:
        existing = Rate.search([
            ('currency_id', '=', currency.id),
            ('company_id', '=', company.id),
            ('name', '=', early_date),
        ], limit=1)
        if existing:
            if existing.rate != pivot_rate:
                existing.rate = pivot_rate
                print(f"  [OK] rate updated for {currency.name} / {company.name} on {early_date}")
            else:
                print(f"  [SKIP] rate already correct for {currency.name} / {company.name} on {early_date}")
            continue
        Rate.create({
            'currency_id': currency.id,
            'company_id': company.id,
            'name': early_date,
            'rate': pivot_rate,
        })
        print(f"  [OK] rate created for {currency.name} / {company.name} on {early_date}")
env.cr.commit()

for company in (areks, evoco):
    usd_to_try = USD._convert(1, TRY, company, today)
    eur_to_try = EUR._convert(1, TRY, company, today)
    print(f"  [CHECK] {company.name}: 1 USD = {usd_to_try} TRY, 1 EUR = {eur_to_try} TRY")
    assert abs(usd_to_try - 34.50) < 0.01, f"USD->TRY conversion wrong for {company.name}: {usd_to_try}"
    assert abs(eur_to_try - 37.20) < 0.01, f"EUR->TRY conversion wrong for {company.name}: {eur_to_try}"

# --- Turkish chart of accounts for both companies ---
ChartTemplate = env['account.chart.template'].sudo()
for company in (areks, evoco):
    if company.chart_template == 'tr':
        print(f"  [SKIP] {company.name} already has 'tr' chart template")
        continue
    print(f"  [LOADING] Turkish chart of accounts for {company.name} ...")
    ChartTemplate.try_loading('tr', company, install_demo=False, force_create=True)
    env.cr.commit()
    company_check = Company.browse(company.id)
    print(f"  [OK] {company.name} chart_template={company_check.chart_template}")

# --- PO double validation: two-step approval above 250,000 TRY ---
for company in (areks, evoco):
    company.write({
        'po_double_validation': 'two_step',
        'po_double_validation_amount': 250000.0,
    })
    print(f"  [OK] {company.name}: po_double_validation=two_step, threshold=250000 TRY")
env.cr.commit()

# --- Fix Areks's default pricelist currency (leftover from when it was
# a USD company before Section 2 changed its currency to TRY - its
# auto-created "Default USD" pricelist never got updated, so every new
# customer silently defaulted to USD quotes/orders until this was
# found and fixed) ---
Pricelist = env['product.pricelist'].sudo()
areks_pricelists = Pricelist.search([('company_id', '=', areks.id), ('currency_id', '!=', TRY.id)])
if areks_pricelists:
    areks_pricelists.write({'currency_id': TRY.id})
    print(f"  [OK] fixed {len(areks_pricelists)} Areks pricelist(s) to use TRY "
          f"(was: leftover non-TRY currency from before Areks became a TRY company)")
else:
    print("  [SKIP] Areks pricelists already in TRY")
env.cr.commit()

# --- Grant the platform's own admin login (used by Odoo.sh's backend
# auto-connect URL) access to BOTH companies + the multi-company switcher
# group. Found & fixed: this account pre-dates Evoco (created when there
# was only one company) and was never given access to it or the
# base.group_multi_company group, so the company switcher never showed
# up and Evoco's data was completely inaccessible to it. ---
admin_user = env['res.users'].sudo().search([('login', '=', 'admin')], limit=1)
if admin_user:
    multi_company_group = env.ref('base.group_multi_company')
    vals = {}
    if evoco.id not in admin_user.company_ids.ids:
        vals['company_ids'] = [(4, evoco.id)]
    if not admin_user.has_group('base.group_multi_company'):
        vals['group_ids'] = [(4, multi_company_group.id)]
    if vals:
        admin_user.write(vals)
        print("  [OK] admin login: granted Evoco company access + multi-company group")
    else:
        print("  [SKIP] admin login already has Evoco access + multi-company group")
    env.cr.commit()

# --- Give each company's own partner a valid VAT/VKN (found & fixed:
# res.partner.is_company is COMPUTED from commercial_partner_id==self
# and has_vat, which in turn depends on `vat` being set and
# checksum-valid - so without this, both company partners silently
# showed is_company=False despite being actual companies) ---
if not areks.partner_id.vat:
    areks.partner_id.vat = '1000000113'
    print("  [OK] set Areks partner VAT/VKN (fixes is_company compute)")
else:
    print("  [SKIP] Areks partner already has a VAT/VKN")
if not evoco.partner_id.vat:
    evoco.partner_id.vat = '1000000121'
    print("  [OK] set Evoco partner VAT/VKN (fixes is_company compute)")
else:
    print("  [SKIP] Evoco partner already has a VAT/VKN")
env.cr.commit()

# --- Disable SMS delivery confirmation (found enabled by default on
# Areks / ex-"YourCompany" - it pops an interactive "confirm.stock.sms"
# wizard on every stock.picking.button_validate(), which silently
# blocked a fully-scripted delivery flow until found & disabled here) ---
for company in (areks, evoco):
    if company.stock_text_confirmation:
        company.stock_text_confirmation = False
        print(f"  [OK] {company.name}: disabled stock SMS delivery confirmation")
    else:
        print(f"  [SKIP] {company.name}: stock SMS delivery confirmation already off")
env.cr.commit()

# --- Warehouses: one-step receipt & delivery ---
# NOTE: code is only unique PER COMPANY (code, company_id) - must scope
# the search by company_id too, otherwise this matches the archived old
# company's same-coded warehouse instead of creating a fresh one here.
areks_wh = Warehouse.search([('code', '=', 'ARK'), ('company_id', '=', areks.id)], limit=1)
if not areks_wh:
    # the existing default warehouse created automatically for the first company
    legacy_wh = Warehouse.search([('company_id', '=', areks.id)], limit=1)
    if legacy_wh:
        legacy_wh.write({
            'name': 'Areks Kurtköy',
            'code': 'ARK',
            'reception_steps': 'one_step',
            'delivery_steps': 'ship_only',
        })
        areks_wh = legacy_wh
        print(f"  [OK] renamed Areks default warehouse -> {areks_wh.name} ({areks_wh.code})")
    else:
        areks_wh = Warehouse.create({
            'name': 'Areks Kurtköy',
            'code': 'ARK',
            'company_id': areks.id,
            'reception_steps': 'one_step',
            'delivery_steps': 'ship_only',
        })
        print(f"  [OK] created Areks warehouse {areks_wh.name} ({areks_wh.code})")
else:
    print(f"  [SKIP] Areks warehouse ARK already exists (id={areks_wh.id})")

evoco_wh = Warehouse.search([('code', '=', 'EVK'), ('company_id', '=', evoco.id)], limit=1)
if not evoco_wh:
    legacy_wh = Warehouse.search([('company_id', '=', evoco.id)], limit=1)
    if legacy_wh:
        legacy_wh.write({
            'name': 'Evoco Kurtköy',
            'code': 'EVK',
            'reception_steps': 'one_step',
            'delivery_steps': 'ship_only',
        })
        evoco_wh = legacy_wh
        print(f"  [OK] renamed Evoco default warehouse -> {evoco_wh.name} ({evoco_wh.code})")
    else:
        evoco_wh = Warehouse.create({
            'name': 'Evoco Kurtköy',
            'code': 'EVK',
            'company_id': evoco.id,
            'reception_steps': 'one_step',
            'delivery_steps': 'ship_only',
        })
        print(f"  [OK] created Evoco warehouse {evoco_wh.name} ({evoco_wh.code})")
else:
    print(f"  [SKIP] Evoco warehouse EVK already exists (id={evoco_wh.id})")

env.cr.commit()

# --- Areks does not manufacture: disable MTO/manufacture resupply on
# its warehouse (root-cause fix - audit point 3) ---
if areks_wh.manufacture_to_resupply:
    areks_wh.manufacture_to_resupply = False
    print("  [OK] Areks Kurtköy: manufacture_to_resupply disabled (Areks is Buy-only)")
else:
    print("  [SKIP] Areks Kurtköy: manufacture_to_resupply already disabled")
env.cr.commit()

# --- Inter-company sale/purchase sync (sale_purchase_inter_company_rules) ---
# NOTE (version check, Odoo 20.0): this module has NO dedicated
# "intercompany user" or "destination warehouse" fields on res.company.
# Automation runs internally as SUPERUSER_ID, and since each company has
# exactly one warehouse here, the auto-created SO/PO naturally lands on
# that company's single warehouse without needing an explicit field.
for company in (areks, evoco):
    company.write({
        'intercompany_generate_sales_orders': True,
        'intercompany_generate_purchase_orders': True,
        'intercompany_document_state': 'posted',  # auto-confirm the generated SO/PO
        # audit point 4: auto-generate the counterpart vendor bill when an
        # inter-company customer invoice is posted (account_inter_company_rules)
        'intercompany_generate_bills_refund': True,
    })
    print(f"  [OK] {company.name}: inter-company SO/PO sync + auto-bill/refund generation enabled")
env.cr.commit()

print("-" * 70)
print(f"SUMMARY: Areks id={areks.id} currency={areks.currency_id.name} chart={areks.chart_template} warehouse={areks_wh.code}")
print(f"SUMMARY: Evoco id={evoco.id} currency={evoco.currency_id.name} chart={evoco.chart_template} warehouse={evoco_wh.code}")
print("=" * 70)
print("02_companies.py done")
print("=" * 70)
