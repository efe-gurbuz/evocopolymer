"""
10c_manufacturing.py
Evoco historical manufacturing, last ~5 months:
  - Prerequisite sub-assembly MOs (EVO-PE 35, EVO-PMX R) produced via
    real MOs (not injected) so that the Formula-1 EVO-RP 210 MOs are a
    genuine multi-level build, consuming an actual EVO-PMX R batch.
  - 4 MOs of EVO-RP 210 via "Formül 1 – Cyclopentane" (multi-level)
  - 4 MOs of EVO-RP 210 via "Formül 2 – 365MFC" (direct)
  - 4 MOs across other products (EVO-RS 320, EVO-RC 150, EVO-FS 400,
    EVO-SR 500)
All completed (button_mark_done), lots assigned on output, quality
checks (Evoco manufacturing: "Krem süresi (sn)" measure + "Görsel
kontrol" pass/fail, both scoped to the PU Sistemleri category) passed.

Base raw materials are topped up via opening-stock quants whenever
short (reactive, right before each MO needs them) - this is simply
provisioning, same technique used in 10b; it does not fabricate the
sub-assemblies themselves, which are always real MOs.

Idempotent via a unique `origin` marker per MO.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/10c_manufacturing.py
"""

import datetime

print("=" * 70)
print("10c_manufacturing.py starting")
print("=" * 70)

evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
evk = env['stock.warehouse'].sudo().search([('company_id', '=', evoco.id)], limit=1)
loc = evk.lot_stock_id
Product = env['product.template'].sudo()
Bom = env['mrp.bom'].sudo()
Production = env['mrp.production'].sudo().with_company(evoco)
Lot = env['stock.lot'].sudo()
Quant = env['stock.quant'].sudo().with_company(evoco)

today = datetime.date.today()
_topup_counter = {'n': 0}


def evoco_on_hand(variant):
    # NOTE (bug found & fixed): `variant.with_company(evoco).qty_available`
    # does NOT scope by warehouse/location - for a SHARED product
    # (company_id=False) it happily reported Areks's on-hand quantity
    # (sitting in ARK/Stock) as "available" to Evoco, since
    # with_company() only changes the env's active company, not the
    # quant location domain. That caused several MOs below to be
    # under-provisioned (0 or partially consumed components) despite
    # ensure_stock() believing there was "enough". Querying stock.quant
    # directly, scoped to Evoco's own stock location, is the correct
    # company-safe check.
    quants = env['stock.quant'].sudo().search([
        ('product_id', '=', variant.id),
        ('location_id', 'child_of', loc.id),
    ])
    return sum(quants.mapped('quantity'))


def ensure_stock(name, qty_needed, buffer=1.2):
    variant = Product.search([('name', '=', name)], limit=1).product_variant_id
    have = evoco_on_hand(variant)
    if have >= qty_needed:
        return
    need = round((qty_needed - have) * buffer + 10, 2)
    _topup_counter['n'] += 1
    # audit point 1: never set company_id on a lot.
    lot = Lot.create({
        'name': f"EVK-OPEN-{_topup_counter['n']:03d}",
        'product_id': variant.id,
    })
    Quant._update_available_quantity(variant, loc, need, lot_id=lot)
    print(f"    [OK] topped up {need} kg of {name} at Evoco (opening stock)")


def pass_quality_checks(mo):
    for check in mo.check_ids:
        if check.quality_state != 'none':
            continue
        if check.test_type == 'measure':
            # within our configured tolerances (Krem suresi 8-20sn)
            check.measure = 14
            check.do_measure()
        elif check.test_type == 'passfail':
            check.do_pass()
        else:
            check.do_pass()


def run_mo(marker, product_code, qty, backdate, bom_code=None):
    # audit-rebuild fix: a marker match alone can hit a leftover MO
    # still sitting under the OLD (now archived/renamed) company id.
    existing = Production.search([('origin', '=', marker), ('company_id', '=', evoco.id)], limit=1)
    if existing:
        print(f"  [SKIP] {marker} already exists ({existing.name})")
        return existing

    prod_tmpl = Product.search([('default_code', '=', product_code)], limit=1)
    domain = [('product_tmpl_id', '=', prod_tmpl.id)]
    if bom_code:
        domain.append(('code', '=', bom_code))
    bom = Bom.search(domain, limit=1)
    assert bom, f"BOM not found for {product_code} / {bom_code}"

    # make sure every component has enough stock at Evoco
    for line in bom.bom_line_ids:
        needed = (line.product_qty / bom.product_qty) * qty
        ensure_stock(line.product_id.name, needed)

    backdate_dt = datetime.datetime.combine(backdate, datetime.time(9, 0))
    mo = Production.create({
        'product_id': prod_tmpl.product_variant_id.id,
        'product_qty': qty,
        'bom_id': bom.id,
        'company_id': evoco.id,
        'date_start': backdate,
        'origin': marker,
    })
    mo.action_confirm()
    mo.action_assign()
    pass_quality_checks(mo)

    # audit point 1: never set company_id on a lot.
    out_lot = Lot.create({
        'name': f"EVK-{product_code.replace(' ', '')}-{marker[-6:]}",
        'product_id': mo.product_id.id,
    })
    mo.lot_producing_ids = [(6, 0, [out_lot.id])]
    mo.qty_producing = qty
    mo.move_raw_ids.write({'picked': True, 'date': backdate})
    mo.move_finished_ids.write({'date': backdate})

    # audit point 7: realistic MO duration from the BOM's "Karıştırma"
    # operation (60/75 min depending on formula) - if Work Orders are
    # enabled, backdate the generated workorder's start/finish/duration
    # to match; the MO header's own dates are set the same way either way.
    mix_op = bom.operation_ids.filtered(lambda o: o.name == 'Karıştırma')
    op_minutes = mix_op[0].time_cycle_manual if mix_op else 60.0
    op_end = backdate_dt + datetime.timedelta(minutes=op_minutes)
    # NOTE (bug found & fixed): writing mo.date_start/date_finished on the
    # MO header itself triggers _unplan_workorders() (any date write is
    # treated as a reschedule), which then refuses because the workorder
    # "already started" (we just set its own dates) - so only the
    # workorder's own dates/duration are backdated; the MO header keeps
    # the date_start it got at create() and gets its date_finished
    # naturally from button_mark_done().
    if mo.workorder_ids:
        for wo in mo.workorder_ids:
            wo.write({
                'date_start': backdate_dt,
                'date_finished': op_end,
                'duration': op_minutes,
            })

    mo.button_mark_done()
    env.cr.commit()
    print(f"  [OK] {marker}: {product_code} x{qty}kg via {bom.code!r} -> {mo.name} ({mo.state})")
    return mo


# -----------------------------------------------------------------------
# Prerequisite sub-assemblies (real MOs, not injected)
# -----------------------------------------------------------------------
for i in range(2):
    run_mo(f"EVOCO-PRE-PE35-{i:02d}", "EVO-PE 35", 1000.0,
           today - datetime.timedelta(days=150 - i * 5), bom_code="EVO-PE 35 - Standart")

for i in range(5):
    run_mo(f"EVOCO-PRE-PMXR-{i:02d}", "EVO-PMX R", 940.0,
           today - datetime.timedelta(days=140 - i * 5), bom_code="EVO-PMX R - Standart")

# -----------------------------------------------------------------------
# 4 MOs: EVO-RP 210 via Formula 1 (multi-level: consumes EVO-PMX R)
# -----------------------------------------------------------------------
for i in range(4):
    run_mo(f"EVOCO-RP210-F1-{i:02d}", "EVO-RP 210", 1000.0,
           today - datetime.timedelta(days=110 - i * 10), bom_code="Formül 1 – Cyclopentane")

# -----------------------------------------------------------------------
# 4 MOs: EVO-RP 210 via Formula 2 (direct)
# -----------------------------------------------------------------------
for i in range(4):
    run_mo(f"EVOCO-RP210-F2-{i:02d}", "EVO-RP 210", 1000.0,
           today - datetime.timedelta(days=70 - i * 10), bom_code="Formül 2 – 365MFC")

# -----------------------------------------------------------------------
# 5 MOs across other products (incl. EVO-CE 600 - audit point 11
# requires it to be demonstrably produceable)
# -----------------------------------------------------------------------
OTHERS = ["EVO-RS 320", "EVO-RC 150", "EVO-FS 400", "EVO-SR 500", "EVO-CE 600"]
for i, code in enumerate(OTHERS):
    run_mo(f"EVOCO-OTHER-{i:02d}", code, 1000.0, today - datetime.timedelta(days=30 - i * 5))

print("-" * 70)
total_counted = env['mrp.production'].sudo().search_count([('origin', 'like', 'EVOCO-%'), ('state', '=', 'done')])
print(f"SUMMARY: total done MOs tagged EVOCO-*: {total_counted} (expect 7 prereq + 13 counted = 20)")
print("=" * 70)
print("10c_manufacturing.py done")
print("=" * 70)
