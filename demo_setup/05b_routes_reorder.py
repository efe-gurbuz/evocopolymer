"""
05b_routes_reorder.py
Audit point 3 (ÜRETİM TETİKLEME) + point 6 (TEDARİKÇİ FİYATLARI, Areks
side of it): activates the MTO route and assigns it to Evoco's 6
finished PU systems + EVO-PMX R; gives EVO-PE 35 a min0/max0 Manufacture
reorder rule instead (it feeds EVO-PMX R's MTO chain one level down);
creates a 500/5000kg Buy reorder rule on every Areks raw material Evoco
actually consumes (derived from the BOM lines themselves, not
hardcoded), with Areks Kimya as the (sequence=0, i.e. preferred) vendor
at Areks's own inter-company sale price (cost x 1.10, TRY) - this is
what makes the demo's main storyline (Evoco shortage -> auto
inter-company PO to Areks) actually fire.

Idempotent: search-before-create / write-if-different everywhere.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/05b_routes_reorder.py
"""

print("=" * 70)
print("05b_routes_reorder.py starting")
print("=" * 70)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
assert areks and evoco

Product = env['product.template'].sudo()
Route = env['stock.route'].sudo()
Bom = env['mrp.bom'].sudo()
Warehouse = env['stock.warehouse'].sudo()
Orderpoint = env['stock.warehouse.orderpoint'].sudo()
SupplierInfo = env['product.supplierinfo'].sudo()
TRY = env['res.currency'].sudo().search([('name', '=', 'TRY')], limit=1)
INTERCOMPANY_MARKUP = 1.10  # same markup used in 04_products.py

evoco_wh = Warehouse.search([('company_id', '=', evoco.id)], limit=1)
assert evoco_wh

# -----------------------------------------------------------------------
# 1. Activate the MTO route, assign to 6 Evoco finished goods + EVO-PMX R
# -----------------------------------------------------------------------
mto_route = env.ref('stock.route_warehouse0_mto')
if not mto_route.active:
    mto_route.active = True
    print(f"  [OK] MTO route activated (id={mto_route.id})")
else:
    print(f"  [SKIP] MTO route already active (id={mto_route.id})")

MTO_CODES = ["EVO-RP 210", "EVO-RS 320", "EVO-RC 150", "EVO-FS 400",
             "EVO-SR 500", "EVO-CE 600", "EVO-PMX R"]
for code in MTO_CODES:
    prod = Product.search([('default_code', '=', code)], limit=1)
    assert prod, f"product not found: {code}"
    if mto_route not in prod.route_ids:
        prod.route_ids = [(4, mto_route.id)]
        print(f"  [OK] MTO route assigned: {prod.name} ({code})")
    else:
        print(f"  [SKIP] MTO route already assigned: {prod.name} ({code})")

env.cr.commit()

# -----------------------------------------------------------------------
# 2. Areks warehouse: manufacture_to_resupply must stay False (also set
#    in 02_companies.py - re-asserted here defensively)
# -----------------------------------------------------------------------
areks_wh = Warehouse.search([('company_id', '=', areks.id)], limit=1)
assert areks_wh
if areks_wh.manufacture_to_resupply:
    areks_wh.manufacture_to_resupply = False
    print("  [FIX] Areks warehouse manufacture_to_resupply forced back to False")
else:
    print("  [SKIP] Areks warehouse manufacture_to_resupply already False")

# -----------------------------------------------------------------------
# 3. EVO-PE 35: min0/max0 Manufacture reorder rule (not MTO route)
# -----------------------------------------------------------------------
manufacture_route = Route.search([('name', '=', 'Manufacture')], limit=1)
buy_route = Route.search([('name', '=', 'Buy')], limit=1)
assert manufacture_route and buy_route

evo_pe35 = Product.search([('default_code', '=', 'EVO-PE 35')], limit=1)
op = Orderpoint.search([
    ('product_id', '=', evo_pe35.product_variant_id.id),
    ('warehouse_id', '=', evoco_wh.id),
], limit=1)
if not op:
    op = Orderpoint.create({
        'name': 'EVO-PE 35 - Manufacture (min0/max0)',
        'warehouse_id': evoco_wh.id,
        'location_id': evoco_wh.lot_stock_id.id,
        'product_id': evo_pe35.product_variant_id.id,
        'product_min_qty': 0.0,
        'product_max_qty': 0.0,
        'route_id': manufacture_route.id,
        'company_id': evoco.id,
        # audit tur 2, point 4: live demoda siparişler Yenileme
        # ekranından manuel verilecek - otomatik tetiklenmesin.
        'trigger': 'manual',
    })
    print(f"  [OK] reorder rule created: EVO-PE 35 (min0/max0/Manufacture, id={op.id})")
else:
    fix_vals = {}
    if op.product_min_qty != 0.0:
        fix_vals['product_min_qty'] = 0.0
    if op.product_max_qty != 0.0:
        fix_vals['product_max_qty'] = 0.0
    if op.route_id != manufacture_route:
        fix_vals['route_id'] = manufacture_route.id
    if op.trigger != 'manual':
        fix_vals['trigger'] = 'manual'
    if fix_vals:
        op.write(fix_vals)
        print(f"  [FIX] reorder rule corrected: EVO-PE 35 -> {fix_vals}")
    else:
        print(f"  [SKIP] reorder rule exists: EVO-PE 35 (id={op.id})")

env.cr.commit()

# -----------------------------------------------------------------------
# 4. Derive every Areks raw material Evoco's BOMs actually consume
#    (any BOM line component belonging to one of the 3 Areks hammadde
#    categories, across all of Evoco's BOMs incl. the phantom kit BOM)
# -----------------------------------------------------------------------
hammadde_categs = env['product.category'].sudo().search(
    [('name', 'in', ['Polioller', 'İzosiyanatlar', 'Yardımcı Kimyasallar'])])
assert len(hammadde_categs) == 3

evoco_boms = Bom.search([('company_id', '=', evoco.id)])
raw_materials_used = env['product.template'].sudo().browse()
for bom in evoco_boms:
    for line in bom.bom_line_ids:
        tmpl = line.product_id.product_tmpl_id
        if tmpl.categ_id in hammadde_categs and tmpl not in raw_materials_used:
            raw_materials_used |= tmpl

print(f"  [INFO] {len(raw_materials_used)} distinct Areks raw materials consumed by Evoco's BOMs: "
      f"{sorted(raw_materials_used.mapped('name'))}")

# -----------------------------------------------------------------------
# 5. Areks-as-preferred-vendor supplierinfo for Evoco (company_id=evoco,
#    sequence=0), at Areks's own inter-company sale price (cost x 1.10)
# -----------------------------------------------------------------------
sup_created, sup_fixed, sup_skipped = 0, 0, 0
for tmpl in raw_materials_used:
    areks_cost = tmpl.with_company(areks).standard_price
    sale_price = round(areks_cost * INTERCOMPANY_MARKUP, 2)
    existing = SupplierInfo.search([
        ('product_tmpl_id', '=', tmpl.id),
        ('partner_id', '=', areks.partner_id.id),
        ('company_id', '=', evoco.id),
    ], limit=1)
    if not existing:
        SupplierInfo.create({
            'product_tmpl_id': tmpl.id,
            'partner_id': areks.partner_id.id,
            'company_id': evoco.id,
            'sequence': 0,
            'price': sale_price,
            'currency_id': TRY.id,
            'min_qty': 0.0,
            'delay': 2,
        })
        sup_created += 1
    else:
        fix_vals = {}
        if existing.sequence != 0:
            fix_vals['sequence'] = 0
        if abs(existing.price - sale_price) > 0.001:
            fix_vals['price'] = sale_price
        if existing.min_qty != 0.0:
            fix_vals['min_qty'] = 0.0
        if fix_vals:
            existing.write(fix_vals)
            sup_fixed += 1
        else:
            sup_skipped += 1

print(f"  [OK] Areks-as-vendor supplierinfo for Evoco: created={sup_created} "
      f"fixed={sup_fixed} skipped={sup_skipped}")
env.cr.commit()

# -----------------------------------------------------------------------
# 6. 500/5000kg Buy reorder rule on Evoco's warehouse for every one of
#    those raw materials
# -----------------------------------------------------------------------
rr_created, rr_fixed, rr_skipped = 0, 0, 0
for tmpl in raw_materials_used:
    variant = tmpl.product_variant_id
    op = Orderpoint.search([
        ('product_id', '=', variant.id),
        ('warehouse_id', '=', evoco_wh.id),
    ], limit=1)
    if not op:
        Orderpoint.create({
            'name': f"{tmpl.name} - Buy (min500/max5000)",
            'warehouse_id': evoco_wh.id,
            'location_id': evoco_wh.lot_stock_id.id,
            'product_id': variant.id,
            'product_min_qty': 500.0,
            'product_max_qty': 5000.0,
            'route_id': buy_route.id,
            'company_id': evoco.id,
            # audit tur 2, point 4: manual trigger - live demoda Yenileme
            # ekranından sipariş verilecek.
            'trigger': 'manual',
        })
        rr_created += 1
    else:
        fix_vals = {}
        if op.product_min_qty != 500.0:
            fix_vals['product_min_qty'] = 500.0
        if op.product_max_qty != 5000.0:
            fix_vals['product_max_qty'] = 5000.0
        if op.route_id != buy_route:
            fix_vals['route_id'] = buy_route.id
        if op.trigger != 'manual':
            fix_vals['trigger'] = 'manual'
        if fix_vals:
            op.write(fix_vals)
            rr_fixed += 1
        else:
            rr_skipped += 1

print(f"  [OK] Evoco raw-material reorder rules: created={rr_created} fixed={rr_fixed} skipped={rr_skipped}")
env.cr.commit()

print("-" * 70)
print("SUMMARY:")
print(f"  MTO route active: {mto_route.active}")
print(f"  Products on MTO route: {MTO_CODES}")
print(f"  Areks warehouse manufacture_to_resupply: {areks_wh.manufacture_to_resupply}")
print(f"  Evoco reorder rules total: {Orderpoint.search_count([('warehouse_id', '=', evoco_wh.id)])}")
print(f"  Areks-as-vendor supplierinfo rows (company_id=evoco): "
      f"{SupplierInfo.search_count([('company_id', '=', evoco.id), ('partner_id', '=', areks.partner_id.id)])}")
print("=" * 70)
print("05b_routes_reorder.py done")
print("=" * 70)
