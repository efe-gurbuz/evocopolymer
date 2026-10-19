"""
04_products.py
All Areks Group products: Areks trade raw materials (4a), Evoco
manufactured semi-finished/finished goods incl. one Kit (4b), and
landed-cost service products (4c).

All products are shared across companies (company_id=False).
Idempotent: search by name (+ default_code where given) before create.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/04_products.py
"""

print("=" * 70)
print("04_products.py starting")
print("=" * 70)

Product = env['product.template'].sudo()
Category = env['product.category'].sudo()
Route = env['stock.route'].sudo()

KG = env['uom.uom'].sudo().browse(201)
UNITS = env['uom.uom'].sudo().browse(186)
assert KG.name == 'kg' and UNITS.name == 'Units'

cat_polioller = Category.search([('name', '=', 'Polioller')], limit=1)
cat_izosiyanat = Category.search([('name', '=', 'İzosiyanatlar')], limit=1)
cat_yardimci = Category.search([('name', '=', 'Yardımcı Kimyasallar')], limit=1)
cat_yari_mamul = Category.search([('name', '=', 'Yarı Mamul')], limit=1)
cat_pu_sistem = Category.search([('name', '=', 'PU Sistemleri')], limit=1)
cat_ithalat = Category.search([('name', '=', 'İthalat Masrafları')], limit=1)
for c in (cat_polioller, cat_izosiyanat, cat_yardimci, cat_yari_mamul, cat_pu_sistem, cat_ithalat):
    assert c, "a required product category is missing - run 03_categories.py first"

# NOTE (version check, Odoo 20.0): Buy/Manufacture routes have
# product_selectable=False here - they are enabled per WAREHOUSE
# (stock.warehouse.buy_to_resupply / manufacture_to_resupply, both
# already True for ARK/EVK from their default one-step config) rather
# than toggled per product via route_ids. Only Dropship remains
# product_selectable=True; it will be added explicitly to route_ids
# only for the specific demo products that need it (later section),
# not here. So no route_ids are set on products in this script.
route_dropship = Route.search([('name', '=', 'Dropship')], limit=1)
assert route_dropship

USD_TO_TRY = 34.50
MARKUP = 1.18
INTERCOMPANY_MARKUP = 1.10  # audit point 2: Evoco's cost for Areks-sourced
                             # raw materials = Areks's own cost x 1.10

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
assert areks and evoco, "companies not found - run 02_companies.py first"

created = []
skipped = []


def get_or_create_product(name, vals, default_code=None):
    domain = [('name', '=', name)]
    if default_code:
        domain = ['&'] + domain + [('default_code', '=', default_code)]
    existing = Product.search(domain, limit=1)
    if existing:
        skipped.append(name)
        print(f"  [SKIP] product exists: {name}")
        return existing
    vals = dict(vals, name=name, company_id=False)
    if default_code:
        vals['default_code'] = default_code
    prod = Product.create(vals)
    created.append(name)
    print(f"  [OK] product created: {name} (id={prod.id})")
    return prod


def set_company_cost(product, company, cost_try):
    # NOTE (audit root-cause fix): product.template.standard_price proxies
    # a COMPUTED field that delegates to product.product.standard_price,
    # which IS company_dependent=True (verified: product.template's own
    # field is company_dependent=False, but the underlying variant field
    # it computes from is True) - so the only correct way to give each
    # company its own cost is to write it via with_company(company).
    prod_c = product.with_company(company)
    if abs((prod_c.standard_price or 0.0) - cost_try) > 0.001:
        prod_c.standard_price = cost_try


# -----------------------------------------------------------------------
# 4a. Areks commercial raw materials (route: Buy), USD/kg cost -> TRY
# -----------------------------------------------------------------------
AREKS_PRODUCTS = [
    ("Konvansiyonel Şeffaf Polyol", cat_polioller, 1.65),
    ("%15 Polimerik Polyol (POP)", cat_polioller, 1.85),
    ("%25 Polimerik Polyol (POP)", cat_polioller, 1.95),
    ("%40 Polimerik Polyol (POP)", cat_polioller, 2.10),
    ("R4110", cat_polioller, 1.70),
    ("Semi-Rigid Poliol", cat_polioller, 1.80),
    ("Poliester Poliol 35 OH 4500mw", cat_polioller, 2.20),
    ("Poliester Poliol C220 - LE220A", cat_polioller, 2.30),
    ("TDI", cat_izosiyanat, 2.25),
    ("Polimerik MDI", cat_izosiyanat, 2.05),
    ("Monomerik MDI", cat_izosiyanat, 2.60),
    ("Modifiye MDI", cat_izosiyanat, 2.75),
    ("Cyclopentane", cat_yardimci, 2.40),
    ("N-Pentane", cat_yardimci, 2.20),
    ("Metylal (Pure) 05050", cat_yardimci, 2.90),
    ("365MFC", cat_yardimci, 8.20),
    ("245FA", cat_yardimci, 9.10),
    ("Flexible Slabstock Katalist", cat_yardimci, 7.50),
    ("Rigid Grup Katalist", cat_yardimci, 7.20),
    ("Flexible Slabstock Silikon", cat_yardimci, 6.40),
    ("Rigid Grup Silikon", cat_yardimci, 6.10),
    ("Yanmazlık TCPP", cat_yardimci, 1.85),
    ("Yanmazlık TEP", cat_yardimci, 2.05),
    ("Kalıp Ayırıcı Sintaliz 6006", cat_yardimci, 4.80),
    ("Renk Pastası", cat_yardimci, 5.50),
    ("Adipik Asit", cat_yardimci, 1.60),
    ("Dietilen Glikol (DEG)", cat_yardimci, 1.10),
]

areks_products_by_name = {}
for name, categ, cost_usd in AREKS_PRODUCTS:
    cost_try_areks = round(cost_usd * USD_TO_TRY, 2)
    price_try = round(cost_try_areks * MARKUP, 2)
    vals = {
        'categ_id': categ.id,
        'type': 'consu',
        'is_storable': True,
        'tracking': 'lot',
        'sale_ok': True,
        'purchase_ok': True,
        'uom_id': KG.id,
        'list_price': price_try,
        'use_expiration_date': True,
        'expiration_time': 365,
        'alert_time': 30,
        'invoice_policy': 'delivery',  # audit point 5
    }
    prod = get_or_create_product(name, vals)
    areks_products_by_name[name] = prod
    # audit point 2: per-company cost - Areks at real cost, Evoco at the
    # inter-company transfer price (+10%), so Evoco's stock value is
    # never 0 even before any real inter-company transaction occurs.
    set_company_cost(prod, areks, cost_try_areks)
    set_company_cost(prod, evoco, round(cost_try_areks * INTERCOMPANY_MARKUP, 2))

env.cr.commit()
print("  [OK] per-company costs set for all 27 raw materials (Areks cost, Evoco = Areks x 1.10)")

# -----------------------------------------------------------------------
# 4b. Evoco manufactured products (route: Manufacture), demo TRY prices
# (no source USD cost given for these -> reasonable placeholder TRY
# prices; real cost will be recomputed by AVCO once MOs are completed
# in a later section).
# -----------------------------------------------------------------------
EVOCO_PRODUCTS = [
    # code, name, category, list_price_try, sale_ok
    # NOTE (audit point 2): standard_price is intentionally NOT set here -
    # these are BOM-produced goods, so their cost is computed from the
    # BOM's component costs once 05_boms.py has created the recipes (see
    # the cost-recompute pass at the end of 05_boms.py). A temporary
    # placeholder is set below (Evoco only) purely so stock valuation is
    # never literally 0 in the window between this script and that pass.
    ("EVO-PE 35", "Poliester Poliol EVO-PE 35", cat_yari_mamul, 70.0, True),
    ("EVO-PMX R", "Rijit Ön Karışım (kabartıcısız)", cat_yari_mamul, 78.0, True),
    ("EVO-RP 210", "Rijit Panel Sistemi – Komponent A", cat_pu_sistem, 145.0, True),
    ("EVO-RS 320", "Sprey İzolasyon Sistemi – Komponent A", cat_pu_sistem, 150.0, True),
    ("EVO-RC 150", "Soğutma Sistemi – Komponent A", cat_pu_sistem, 135.0, True),
    ("EVO-FS 400", "Esnek Köpük Sistemi – Komponent A", cat_pu_sistem, 120.0, True),
    ("EVO-SR 500", "Semi-Rigid Sistem – Komponent A", cat_pu_sistem, 130.0, True),
    ("EVO-CE 600", "CASE Elastomer Sistemi – Komponent A", cat_pu_sistem, 140.0, True),
]

evoco_products_by_code = {}
for code, name, categ, price_try, sale_ok in EVOCO_PRODUCTS:
    vals = {
        'categ_id': categ.id,
        'type': 'consu',
        'is_storable': True,
        'tracking': 'lot',
        'sale_ok': sale_ok,
        'purchase_ok': True,  # blanket rule: all stocked products purchasable too
        'uom_id': KG.id,
        'list_price': price_try,
        'use_expiration_date': False,
        'invoice_policy': 'delivery',  # audit point 5
    }
    prod = get_or_create_product(name, vals, default_code=code)
    evoco_products_by_code[code] = prod
    set_company_cost(prod, evoco, round(price_try * 0.75, 2))  # placeholder, replaced in 05_boms.py

env.cr.commit()

# --- EVO-RP 210 SET (Kit: 1000kg EVO-RP 210 + 1100kg Polimerik MDI) ---
# Kit products are phantom-BOM bundles: they do not carry their own stock
# (is_storable=False), are sold as 1 unit ("Set"), and explode into their
# component lines (with their own lot tracking) at delivery time.
rp210 = evoco_products_by_code["EVO-RP 210"]
mdi = areks_products_by_name["Polimerik MDI"]
set_list_price = round(rp210.list_price * 1000 + mdi.list_price * 1100, 2)
set_cost_price = round(
    rp210.with_company(evoco).standard_price * 1000
    + mdi.with_company(evoco).standard_price * 1100, 2)
kit_vals = {
    'categ_id': cat_pu_sistem.id,
    'type': 'consu',
    'is_storable': False,
    'sale_ok': True,
    'purchase_ok': False,
    'uom_id': UNITS.id,
    'list_price': set_list_price,
    'use_expiration_date': False,
}
rp210_set = get_or_create_product(
    "Rijit Panel Sistemi A+B Seti", kit_vals, default_code="EVO-RP 210 SET")
evoco_products_by_code["EVO-RP 210 SET"] = rp210_set
set_company_cost(rp210_set, evoco, set_cost_price)  # recomputed properly in 05_boms.py too
env.cr.commit()

# -----------------------------------------------------------------------
# 4c. Landed-cost service products
# -----------------------------------------------------------------------
SERVICE_PRODUCTS = [
    ("Gümrük Vergisi", 'by_current_cost_price'),
    ("Navlun", 'by_weight'),
    ("Gümrük Müşavirlik Hizmeti", 'equal'),
]
service_products_by_name = {}
for name, split_method in SERVICE_PRODUCTS:
    vals = {
        'categ_id': cat_ithalat.id,
        'type': 'service',
        'sale_ok': False,
        'purchase_ok': True,
        'uom_id': UNITS.id,
        'landed_cost_ok': True,
        'split_method_landed_cost': split_method,
    }
    prod = get_or_create_product(name, vals)
    service_products_by_name[name] = prod

env.cr.commit()

print("-" * 70)
print(f"SUMMARY: created={len(created)} skipped(already existed)={len(skipped)}")
print(f"  Areks raw materials: {len(areks_products_by_name)}")
print(f"  Evoco manufactured (incl. kit): {len(evoco_products_by_code)}")
print(f"  Service products: {len(service_products_by_name)}")
total = Product.search_count([('company_id', '=', False)])
print(f"  Total shared (company_id=False) products in DB: {total}")
print("=" * 70)
print("04_products.py done")
print("=" * 70)
