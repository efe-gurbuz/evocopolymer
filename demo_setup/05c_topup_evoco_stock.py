"""
05c_topup_evoco_stock.py
Audit tur 2, point 4: top up every Evoco raw material EXCEPT R4110 and
Yanmazlık TCPP (which must stay short, per audit point 11's main demo
storyline) to its reorder rule's max level, via a REAL today-dated
inter-company purchase from Areks (Evoco PO -> auto Areks SO -> Areks
delivery with lot -> Evoco receipt with lot + quality check -> done),
not a bare quant adjustment.

Idempotent: tops up only the remaining shortfall to max each run (a
re-run when already at/above max is a no-op).

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/05c_topup_evoco_stock.py
"""

import datetime

print("=" * 70)
print("05c_topup_evoco_stock.py starting")
print("=" * 70)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
assert areks and evoco

evk = env['stock.warehouse'].sudo().search([('company_id', '=', evoco.id)], limit=1)
Orderpoint = env['stock.warehouse.orderpoint'].sudo()
today = datetime.date.today()

EXCLUDE = {'R4110', 'Yanmazlık TCPP'}

orderpoints = Orderpoint.search([
    ('warehouse_id', '=', evk.id), ('route_id.name', '=', 'Buy'),
]).filtered(lambda op: op.product_id.name not in EXCLUDE)
print(f"  {len(orderpoints)} Buy reorder rules to top up to max (excluding {EXCLUDE})")


def on_hand(variant):
    return sum(env['stock.quant'].sudo().search([
        ('product_id', '=', variant.id), ('location_id', 'child_of', evk.lot_stock_id.id),
    ]).mapped('quantity'))


def pass_quality_checks(picking):
    for check in env['quality.check'].sudo().search([
        ('picking_id', '=', picking.id), ('quality_state', '=', 'none'),
    ]):
        if check.test_type == 'measure':
            check.measure = 1.1
            check.do_measure()
        else:
            check.do_pass()


topped_up = 0
skipped = 0
for op in orderpoints:
    variant = op.product_id
    have = on_hand(variant)
    need = round(op.product_max_qty - have, 2)
    if need <= 1:
        print(f"  [SKIP] {variant.name}: already at/near max ({have}kg)")
        skipped += 1
        continue

    marker = f"EVOCO-TOPUP-{variant.id}-{today.isoformat()}"
    existing_po = env['purchase.order'].sudo().with_company(evoco).search(
        [('partner_ref', '=', marker), ('company_id', '=', evoco.id)], limit=1)
    if existing_po:
        po = existing_po
        print(f"  [SKIP] PO already exists for {variant.name}: {po.name}")
    else:
        price = variant.product_tmpl_id.with_company(evoco).standard_price
        po = env['purchase.order'].sudo().with_company(evoco).create({
            'partner_id': areks.partner_id.id,
            'company_id': evoco.id,
            'partner_ref': marker,
            'date_order': today,
            'order_line': [(0, 0, {
                'product_id': variant.id,
                'product_qty': need,
                'price_unit': price,
            })],
        })
        po.button_confirm()
        if po.state == 'to approve':
            po.button_approve()
        # commit right after PO confirm/approve (which is what actually
        # triggers the auto-SO generation at Areks) so a later crash during
        # delivery/receipt can never roll back the PO itself - the search
        # above (by partner_ref marker) then correctly finds it as
        # "existing" on retry instead of creating a conflicting duplicate.
        env.cr.commit()
        print(f"  [OK] PO created: {po.name} -> {variant.name} x{need}kg ({po.state})")

    # Areks side: the auto-generated SO is linked via auto_purchase_order_id
    # (NOT a fuzzy same-product/partner search - that previously matched
    # an unrelated pre-existing small sale instead of this PO's own SO).
    auto_so = env['sale.order'].sudo().search([('auto_purchase_order_id', '=', po.id)], limit=1)
    if auto_so and auto_so.state not in ('sale', 'done'):
        auto_so.action_confirm()
    def force_fulfill(mv, lot_prefix):
        # NOTE (bug found & fixed): action_assign() can leave move_line_ids
        # completely EMPTY when there is nothing to reserve at the source
        # location yet (e.g. the counterpart delivery hasn't run) - a
        # "for ml in mv.move_line_ids" loop then does nothing at all,
        # leaving quantity_done=0 and button_validate() raising the
        # "zero quantity transfer" error. Explicitly create a move line
        # when none exists (same pattern as 10c_fix_stuck_mos.py).
        if mv.product_id.tracking != 'none':
            lot = env['stock.lot'].sudo().create(
                {'name': f"{lot_prefix}-{variant.id}-{mv.id}", 'product_id': mv.product_id.id})
        else:
            lot = False
        if mv.move_line_ids:
            for ml in mv.move_line_ids:
                if lot and not ml.lot_id:
                    ml.lot_id = lot.id
                ml.quantity = ml.quantity or mv.product_uom_qty
        else:
            env['stock.move.line'].sudo().create({
                'move_id': mv.id,
                'product_id': mv.product_id.id,
                'quantity': mv.product_uom_qty,
                'lot_id': lot.id if lot else False,
                'location_id': mv.location_id.id,
                'location_dest_id': mv.location_dest_id.id,
            })

    if auto_so:
        for p in auto_so.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
            p.action_assign()
            for mv in p.move_ids:
                mv.picked = True
                force_fulfill(mv, "ARK-TOPUP")
            p.move_ids.write({'date': today})
            p.button_validate()

    # Evoco side: receive the auto PO, with lot + quality check
    for p in po.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
        p.action_assign()
        for mv in p.move_ids:
            mv.picked = True
            force_fulfill(mv, "EVK-TOPUP")
        p.move_ids.write({'date': today})
        p.button_validate()
        pass_quality_checks(p)

    env.cr.commit()
    new_on_hand = on_hand(variant)
    print(f"    -> {variant.name} on-hand now {new_on_hand}kg (target max {op.product_max_qty}kg)")
    topped_up += 1

print("-" * 70)
print(f"SUMMARY: topped_up={topped_up} skipped(already at max)={skipped}")
for op in orderpoints:
    print(f"   {op.product_id.name:40s} on_hand={round(on_hand(op.product_id), 2)} max={op.product_max_qty}")
print("=" * 70)
print("05c_topup_evoco_stock.py done")
print("=" * 70)
