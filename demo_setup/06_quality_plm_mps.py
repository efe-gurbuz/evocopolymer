"""
06_quality_plm_mps.py
Quality control points (Evoco receipt + manufacturing), PLM ECO
("Formül Revizyonu" type, EVO-RP 210 Formula 2 revision in progress),
and MPS demand forecast for EVO-RP 210 / EVO-FS 400 (next 3 months).

Idempotent: search-before-create everywhere.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/06_quality_plm_mps.py
"""

print("=" * 70)
print("06_quality_plm_mps.py starting")
print("=" * 70)

evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
Product = env['product.template'].sudo()
Category = env['product.category'].sudo()
PickingType = env['stock.picking.type'].sudo()
QualityPoint = env['quality.point'].sudo()
TestType = env['quality.point.test_type'].sudo()

# -----------------------------------------------------------------------
# Quality control points
# -----------------------------------------------------------------------
cat_hammadde_leaves = Category.search([('name', 'in', ['Polioller', 'İzosiyanatlar', 'Yardımcı Kimyasallar'])])
cat_pu_sistem = Category.search([('name', '=', 'PU Sistemleri')], limit=1)
assert len(cat_hammadde_leaves) == 3 and cat_pu_sistem

evoco_receipts = PickingType.search([('warehouse_id.company_id', '=', evoco.id), ('code', '=', 'incoming')], limit=1)
evoco_manufacturing = PickingType.search([('warehouse_id.company_id', '=', evoco.id), ('code', '=', 'mrp_operation')], limit=1)
assert evoco_receipts and evoco_manufacturing

measure_tt = TestType.search([('technical_name', '=', 'measure')], limit=1)
passfail_tt = TestType.search([('technical_name', '=', 'passfail')], limit=1)
assert measure_tt and passfail_tt


def get_or_create_qp(name, vals):
    existing = QualityPoint.search([('name', '=', name), ('company_id', '=', evoco.id)], limit=1)
    if existing:
        print(f"  [SKIP] quality point exists: {name}")
        return existing
    vals = dict(vals, name=name, company_id=evoco.id)
    qp = QualityPoint.create(vals)
    print(f"  [OK] quality point created: {name} (id={qp.id})")
    return qp


get_or_create_qp("Yoğunluk ölçümü", {
    'apply_to': 'categories',
    'product_category_ids': [(6, 0, cat_hammadde_leaves.ids)],
    'picking_type_ids': [(6, 0, evoco_receipts.ids)],
    'measure_on': 'move_line',
    'test_type_id': measure_tt.id,
    'norm_unit': 'g/cm³',
    'tolerance_min': 0.95,
    'tolerance_max': 1.30,
})

get_or_create_qp("Krem süresi (sn)", {
    'apply_to': 'categories',
    'product_category_ids': [(6, 0, cat_pu_sistem.ids)],
    'picking_type_ids': [(6, 0, evoco_manufacturing.ids)],
    'measure_on': 'operation',
    'test_type_id': measure_tt.id,
    'norm_unit': 'sn',
    'tolerance_min': 8,
    'tolerance_max': 20,
})

get_or_create_qp("Görsel kontrol", {
    'apply_to': 'categories',
    'product_category_ids': [(6, 0, cat_pu_sistem.ids)],
    'picking_type_ids': [(6, 0, evoco_manufacturing.ids)],
    'measure_on': 'operation',
    'test_type_id': passfail_tt.id,
})

env.cr.commit()

# -----------------------------------------------------------------------
# PLM: ECO type "Formül Revizyonu" + ECO for EVO-RP 210 Formula 2
# -----------------------------------------------------------------------
EcoType = env['mrp.eco.type'].sudo()
Eco = env['mrp.eco'].sudo()
EcoStage = env['mrp.eco.stage'].sudo()
Bom = env['mrp.bom'].sudo()

eco_type = EcoType.search([('name', '=', 'Formül Revizyonu')], limit=1)
if not eco_type:
    eco_type = EcoType.create({'name': 'Formül Revizyonu'})
    print(f"  [OK] ECO type created: Formül Revizyonu (id={eco_type.id})")
else:
    print(f"  [SKIP] ECO type exists: Formül Revizyonu (id={eco_type.id})")

in_progress_stage = EcoStage.search([('name', '=', 'In Progress')], limit=1)
assert in_progress_stage, "mrp.eco.stage 'In Progress' not found"

rp210 = Product.search([('default_code', '=', 'EVO-RP 210')], limit=1)
formula2_bom = Bom.search([('product_tmpl_id', '=', rp210.id), ('code', '=', 'Formül 2 – 365MFC')], limit=1)
assert rp210 and formula2_bom

eco_name = "EVO-RP 210 – Formül 2: 365MFC oranı optimizasyonu"
# NOTE: mrp.eco auto-prefixes `name` with a sequence ("ECO0001: ..."), so an
# exact match never hits on re-run - use substring match instead.
eco = Eco.search([('name', 'like', eco_name)], limit=1)
if not eco:
    eco = Eco.create({
        'name': eco_name,
        'type_id': eco_type.id,
        'stage_id': in_progress_stage.id,
        'state': 'progress',
        'company_id': evoco.id,
        'product_tmpl_id': rp210.id,
        'bom_id': formula2_bom.id,
        'note': '365MFC oranı optimizasyonu',
    })
    print(f"  [OK] ECO created: {eco_name} (id={eco.id}, state={eco.state})")
else:
    print(f"  [SKIP] ECO exists: {eco_name} (id={eco.id})")

env.cr.commit()

# -----------------------------------------------------------------------
# MPS: demand forecast for EVO-RP 210 and EVO-FS 400, next 3 months
# -----------------------------------------------------------------------
Schedule = env['mrp.production.schedule'].sudo()
evoco_wh = env['stock.warehouse'].sudo().search([('company_id', '=', evoco.id)], limit=1)
assert evoco_wh

MPS_PLAN = [
    ("EVO-RP 210", [12000, 15000, 18000]),   # kg per month, 3 months
    ("EVO-FS 400", [8000, 9000, 10000]),
]

for code, monthly_qty in MPS_PLAN:
    prod_tmpl = Product.search([('default_code', '=', code)], limit=1)
    assert prod_tmpl, f"product not found for MPS: {code}"
    variant = prod_tmpl.product_variant_id
    sched = Schedule.search([
        ('product_id', '=', variant.id),
        ('warehouse_id', '=', evoco_wh.id),
    ], limit=1)
    if not sched:
        sched = Schedule.create({
            'product_id': variant.id,
            'warehouse_id': evoco_wh.id,
            'company_id': evoco.id,
        })
        print(f"  [OK] MPS schedule created for {code} (id={sched.id})")
    else:
        print(f"  [SKIP] MPS schedule exists for {code} (id={sched.id})")
    for idx, qty in enumerate(monthly_qty):
        sched.set_forecast_qty(idx, qty)
    print(f"    forecast set for {code}: {monthly_qty} (3 months)")

env.cr.commit()

print("-" * 70)
print("SUMMARY:")
print(f"  Quality points (Evoco): {QualityPoint.search_count([('company_id', '=', evoco.id)])}")
print(f"  ECO types: {EcoType.search_count([])}, ECOs: {Eco.search_count([])}")
print(f"  MPS schedules: {Schedule.search_count([])}")
print("=" * 70)
print("06_quality_plm_mps.py done")
print("=" * 70)
