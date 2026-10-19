"""
10c_fix_stuck_mos.py
Repair pass for the 12 EVOCO-* MOs that got stuck in 'progress' because
`ensure_stock()` in 10c_manufacturing.py used a buggy availability
check (see the fix note in that file) and under-provisioned some
components. For each short raw move: top up Evoco's real on-hand stock
(location-scoped, company-safe this time), assign a lot, set the full
expected quantity, and retry button_mark_done().

Idempotent: only acts on EVOCO-* MOs still in 'progress'; running again
after everything is 'done' is a no-op.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/10c_fix_stuck_mos.py
"""

print("=" * 70)
print("10c_fix_stuck_mos.py starting")
print("=" * 70)

evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
evk = env['stock.warehouse'].sudo().search([('company_id', '=', evoco.id)], limit=1)
loc = evk.lot_stock_id
Lot = env['stock.lot'].sudo()
Quant = env['stock.quant'].sudo().with_company(evoco)

mos = env['mrp.production'].sudo().search([
    ('origin', 'like', 'EVOCO-%'), ('state', '=', 'progress'), ('company_id', '=', evoco.id)])
print(f"  found {len(mos)} stuck MOs")

topup_n = 0
for mo in mos:
    for mv in mo.move_raw_ids:
        short = mv.product_uom_qty - mv.quantity
        if short <= 0.01:
            continue
        topup_n += 1
        # audit point 1: never set company_id on a lot.
        lot = Lot.create({
            'name': f"EVK-FIX-{topup_n:03d}",
            'product_id': mv.product_id.id,
        })
        Quant._update_available_quantity(mv.product_id, loc, short + 5, lot_id=lot)
        # assign the shortfall onto the existing move line(s), or create one
        mls = mv.move_line_ids
        if mls:
            ml = mls[0]
            ml.quantity = mv.product_uom_qty
            if not ml.lot_id:
                ml.lot_id = lot.id
        else:
            env['stock.move.line'].sudo().create({
                'move_id': mv.id,
                'product_id': mv.product_id.id,
                'quantity': mv.product_uom_qty,
                'lot_id': lot.id,
                'location_id': mv.location_id.id,
                'location_dest_id': mv.location_dest_id.id,
            })
        mv.picked = True
        print(f"    [OK] topped up {short + 5} kg {mv.product_id.name} for {mo.name}")

    res = mo.button_mark_done()
    if isinstance(res, dict) and res.get('res_model') == 'mrp.consumption.warning':
        # shouldn't happen now that quantities match exactly, but just in
        # case of float rounding, force through via the wizard's own
        # "confirm" (skips the warning, keeps actual consumed quantities)
        wiz = env['mrp.consumption.warning'].browse(res.get('res_id')) if res.get('res_id') else None
        mo.with_context(skip_consumption=True).button_mark_done()
    env.cr.commit()
    print(f"  [OK] {mo.origin}: {mo.name} -> {mo.state}")

print("-" * 70)
remaining = env['mrp.production'].sudo().search_count([('origin', 'like', 'EVOCO-%'), ('state', '!=', 'done')])
print(f"SUMMARY: remaining non-done EVOCO-* MOs: {remaining} (expect 0)")
print("=" * 70)
print("10c_fix_stuck_mos.py done")
print("=" * 70)
