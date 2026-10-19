"""
05_boms.py
Bills of Materials for Evoco's manufactured products (batch size 1000 kg),
including the multi-level EVO-RP 210 "Formula 1" (consumes EVO-PMX R,
itself a BOM'd product) and the EVO-RP 210 SET Kit (phantom BOM).

No work center / operations are defined on purpose (kept simple per task
instructions - BOMs run as single-step production without routing).

Idempotent: search by (product_tmpl_id, code) before create.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/05_boms.py
"""

print("=" * 70)
print("05_boms.py starting")
print("=" * 70)

Product = env['product.template'].sudo()
Bom = env['mrp.bom'].sudo()
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
KG = env['uom.uom'].sudo().browse(201)

# --- Work center: "Karışım Tankı" (audit point 7) ---
Workcenter = env['mrp.workcenter'].sudo()
karisim_tanki = Workcenter.search([('name', '=', 'Karışım Tankı'), ('company_id', '=', evoco.id)], limit=1)
if not karisim_tanki:
    karisim_tanki = Workcenter.create({
        'name': 'Karışım Tankı',
        'company_id': evoco.id,
        'costs_hour': 1500.0,
    })
    print(f"  [OK] work center created: Karışım Tankı (1.500 TRY/saat, id={karisim_tanki.id})")
else:
    print(f"  [SKIP] work center exists: Karışım Tankı (id={karisim_tanki.id})")


def P(name_or_code, by_code=False):
    domain = [('default_code', '=', name_or_code)] if by_code else [('name', '=', name_or_code)]
    prod = Product.search(domain, limit=1)
    assert prod, f"product not found: {name_or_code} (by_code={by_code})"
    return prod


def get_or_create_bom(product_tmpl, qty, lines, code, bom_type='normal', sequence=10, op_minutes=60):
    """lines: list of (product_tmpl, qty)"""
    existing = Bom.search([
        ('product_tmpl_id', '=', product_tmpl.id),
        ('code', '=', code),
    ], limit=1)
    if existing:
        # self-healing: correct sequence / mixing-operation duration if an
        # earlier run created this BOM before those requirements existed.
        fix_vals = {}
        if existing.sequence != sequence:
            fix_vals['sequence'] = sequence
        mix_op = existing.operation_ids.filtered(lambda o: o.name == 'Karıştırma')
        if bom_type != 'phantom':
            if not mix_op:
                fix_vals['operation_ids'] = [(0, 0, {
                    'name': 'Karıştırma',
                    'workcenter_id': karisim_tanki.id,
                    'time_mode': 'manual',
                    'time_cycle_manual': op_minutes,
                })]
            elif mix_op[0].time_cycle_manual != op_minutes:
                fix_vals['operation_ids'] = [(1, mix_op[0].id, {'time_cycle_manual': op_minutes})]
        if fix_vals:
            existing.write(fix_vals)
            print(f"  [FIX] BOM corrected: {product_tmpl.name} / {code} -> "
                  f"seq={sequence}, op={op_minutes}min")
        else:
            print(f"  [SKIP] BOM exists: {product_tmpl.name} / {code}")
        return existing
    bom_line_vals = [
        (0, 0, {'product_id': comp.product_variant_id.id, 'product_qty': comp_qty, 'uom_id': KG.id})
        for comp, comp_qty in lines
    ]
    vals = {
        'product_tmpl_id': product_tmpl.id,
        'product_qty': qty,
        'uom_id': KG.id,
        'type': bom_type,
        'code': code,
        'sequence': sequence,
        'company_id': evoco.id,
        'bom_line_ids': bom_line_vals,
    }
    # audit point 7: "Karıştırma" (Mixing) operation on every real (non-kit)
    # Evoco BOM, on the "Karışım Tankı" work center.
    if bom_type != 'phantom':
        vals['operation_ids'] = [(0, 0, {
            'name': 'Karıştırma',
            'workcenter_id': karisim_tanki.id,
            'time_mode': 'manual',
            'time_cycle_manual': op_minutes,
        })]
    bom = Bom.create(vals)
    print(f"  [OK] BOM created: {product_tmpl.name} / {code} (id={bom.id}, {len(lines)} lines, "
          f"seq={sequence}, op={op_minutes}min)")
    return bom


# --- EVO-PE 35: Adipik Asit 560 + DEG 440 -> 1000 kg ---
evo_pe35 = P("EVO-PE 35", by_code=True)
get_or_create_bom(
    evo_pe35, 1000.0,
    [(P("Adipik Asit"), 560.0), (P("Dietilen Glikol (DEG)"), 440.0)],
    code="EVO-PE 35 - Standart",
)

# --- EVO-PMX R: R4110 600 + EVO-PE 35 200 + TCPP 100 + Rigid Silikon 20 + Rigid Katalist 20 -> 940 kg ---
evo_pmxr = P("EVO-PMX R", by_code=True)
get_or_create_bom(
    evo_pmxr, 940.0,
    [
        (P("R4110"), 600.0),
        (evo_pe35, 200.0),
        (P("Yanmazlık TCPP"), 100.0),
        (P("Rigid Grup Silikon"), 20.0),
        (P("Rigid Grup Katalist"), 20.0),
    ],
    code="EVO-PMX R - Standart",
)

# --- EVO-RP 210: two BOMs (Formula 1 multi-level, Formula 2 direct) -> 1000 kg ---
evo_rp210 = P("EVO-RP 210", by_code=True)
get_or_create_bom(
    evo_rp210, 1000.0,
    [(evo_pmxr, 940.0), (P("Cyclopentane"), 60.0)],
    code="Formül 1 – Cyclopentane",
    sequence=1, op_minutes=60,
)
get_or_create_bom(
    evo_rp210, 1000.0,
    [
        (P("R4110"), 550.0),
        (evo_pe35, 200.0),
        (P("Yanmazlık TCPP"), 100.0),
        (P("Rigid Grup Silikon"), 20.0),
        (P("Rigid Grup Katalist"), 20.0),
        (P("365MFC"), 110.0),
    ],
    code="Formül 2 – 365MFC",
    sequence=2, op_minutes=75,
)

# --- EVO-RS 320: EVO-PMX R 900 + 245FA 100 -> 1000 kg ---
get_or_create_bom(
    P("EVO-RS 320", by_code=True), 1000.0,
    [(evo_pmxr, 900.0), (P("245FA"), 100.0)],
    code="EVO-RS 320 - Standart",
)

# --- EVO-RC 150: R4110 700 + Rigid Silikon 25 + Rigid Katalist 25 + TCPP 150 + Cyclopentane 100 -> 1000 kg ---
get_or_create_bom(
    P("EVO-RC 150", by_code=True), 1000.0,
    [
        (P("R4110"), 700.0),
        (P("Rigid Grup Silikon"), 25.0),
        (P("Rigid Grup Katalist"), 25.0),
        (P("Yanmazlık TCPP"), 150.0),
        (P("Cyclopentane"), 100.0),
    ],
    code="EVO-RC 150 - Standart",
)

# --- EVO-FS 400: Konvansiyonel Şeffaf Polyol 800 + %25 POP 150 + Flexible Silikon 20 + Flexible Katalist 30 -> 1000 kg ---
get_or_create_bom(
    P("EVO-FS 400", by_code=True), 1000.0,
    [
        (P("Konvansiyonel Şeffaf Polyol"), 800.0),
        (P("%25 Polimerik Polyol (POP)"), 150.0),
        (P("Flexible Slabstock Silikon"), 20.0),
        (P("Flexible Slabstock Katalist"), 30.0),
    ],
    code="EVO-FS 400 - Standart",
)

# --- EVO-SR 500: Semi-Rigid Poliol 900 + Flexible Katalist 30 + Renk Pastası 70 -> 1000 kg ---
get_or_create_bom(
    P("EVO-SR 500", by_code=True), 1000.0,
    [
        (P("Semi-Rigid Poliol"), 900.0),
        (P("Flexible Slabstock Katalist"), 30.0),
        (P("Renk Pastası"), 70.0),
    ],
    code="EVO-SR 500 - Standart",
)

# --- EVO-CE 600: Poliester Poliol C220 - LE220A 900 + TEP 100 -> 1000 kg ---
get_or_create_bom(
    P("EVO-CE 600", by_code=True), 1000.0,
    [
        (P("Poliester Poliol C220 - LE220A"), 900.0),
        (P("Yanmazlık TEP"), 100.0),
    ],
    code="EVO-CE 600 - Standart",
)

# --- EVO-RP 210 SET (Kit / phantom BOM): EVO-RP 210 1000 kg + Polimerik MDI 1100 kg, per 1 Set ---
UNITS = env['uom.uom'].sudo().browse(186)
rp210_set = P("EVO-RP 210 SET", by_code=True)
existing_kit_bom = Bom.search([('product_tmpl_id', '=', rp210_set.id), ('type', '=', 'phantom')], limit=1)
if existing_kit_bom:
    print(f"  [SKIP] Kit BOM exists: {rp210_set.name}")
else:
    kit_bom = Bom.create({
        'product_tmpl_id': rp210_set.id,
        'product_qty': 1.0,
        'uom_id': UNITS.id,
        'type': 'phantom',
        'code': 'EVO-RP 210 SET - Kit',
        'company_id': evoco.id,
        'bom_line_ids': [
            (0, 0, {'product_id': evo_rp210.product_variant_id.id, 'product_qty': 1000.0, 'uom_id': KG.id}),
            (0, 0, {'product_id': P("Polimerik MDI").product_variant_id.id, 'product_qty': 1100.0, 'uom_id': KG.id}),
        ],
    })
    print(f"  [OK] Kit BOM created: {rp210_set.name} (id={kit_bom.id})")

env.cr.commit()

# -----------------------------------------------------------------------
# Dependency-ordered cost recompute (audit point 2, second half): replace
# the temporary placeholder costs set in 04_products.py with real
# BOM-derived costs (material lines + "Karıştırma" operation cost on
# Karışım Tankı), written per-company via with_company(evoco) since
# product.product.standard_price is company_dependent. Processed in
# dependency order so each level can consume the already-recomputed cost
# of the level below it (EVO-PE 35 -> EVO-PMX R -> EVO-RP 210 -> the rest
# -> the kit).
# -----------------------------------------------------------------------
print("-" * 70)
print("Recomputing Evoco standard costs from BOM (dependency order):")


def set_company_cost(product, company, cost_try):
    prod_c = product.with_company(company)
    if abs((prod_c.standard_price or 0.0) - cost_try) > 0.001:
        prod_c.standard_price = cost_try


def cost_from_bom(bom):
    material_cost = sum(
        line.product_qty * line.product_id.product_tmpl_id.with_company(evoco).standard_price
        for line in bom.bom_line_ids
    )
    op_cost = sum(
        (op.time_cycle_manual or 0.0) / 60.0 * (op.workcenter_id.costs_hour or 0.0)
        for op in bom.operation_ids
    )
    return round((material_cost + op_cost) / bom.product_qty, 4)


# EVO-RP 210 carries two formulas (sequence 1 = Formül 1, sequence 2 =
# Formül 2); Odoo itself prefers the lowest-sequence BOM when several are
# eligible for the same product with no variant restriction, so Formül 1
# is used as the "standard" costing recipe here too.
RECOMPUTE_ORDER = [
    (evo_pe35, "EVO-PE 35 - Standart"),
    (evo_pmxr, "EVO-PMX R - Standart"),
    (evo_rp210, "Formül 1 – Cyclopentane"),
    (P("EVO-RS 320", by_code=True), "EVO-RS 320 - Standart"),
    (P("EVO-RC 150", by_code=True), "EVO-RC 150 - Standart"),
    (P("EVO-FS 400", by_code=True), "EVO-FS 400 - Standart"),
    (P("EVO-SR 500", by_code=True), "EVO-SR 500 - Standart"),
    (P("EVO-CE 600", by_code=True), "EVO-CE 600 - Standart"),
]
for tmpl, code in RECOMPUTE_ORDER:
    bom = Bom.search([('product_tmpl_id', '=', tmpl.id), ('code', '=', code)], limit=1)
    cost = cost_from_bom(bom)
    set_company_cost(tmpl, evoco, cost)
    print(f"  [OK] {tmpl.name:40s} ({code}) -> cost={cost} TRY/kg")

# Kit, last: depends on the now-final EVO-RP 210 cost + Polimerik MDI
# (an Areks raw material, already costed for Evoco in 04_products.py).
kit_bom = Bom.search([('product_tmpl_id', '=', rp210_set.id), ('type', '=', 'phantom')], limit=1)
kit_material_cost = sum(
    line.product_qty * line.product_id.product_tmpl_id.with_company(evoco).standard_price
    for line in kit_bom.bom_line_ids
)
kit_cost = round(kit_material_cost / kit_bom.product_qty, 4)
set_company_cost(rp210_set, evoco, kit_cost)
print(f"  [OK] {rp210_set.name:40s} (EVO-RP 210 SET - Kit) -> cost={kit_cost} TRY/Units")

env.cr.commit()

print("-" * 70)
all_boms = Bom.search([('company_id', '=', evoco.id)])
print(f"SUMMARY: {len(all_boms)} BOMs for Evoco")
for b in all_boms:
    print(f"   {b.product_tmpl_id.name:45s} [{b.code}] type={b.type} seq={b.sequence} "
          f"qty={b.product_qty}{b.uom_id.name} lines={len(b.bom_line_ids)} "
          f"ops={[(o.name, o.time_cycle_manual) for o in b.operation_ids]}")
print("=" * 70)
print("05_boms.py done")
print("=" * 70)
