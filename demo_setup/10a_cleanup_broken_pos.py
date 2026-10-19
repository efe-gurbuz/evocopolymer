"""
10a_cleanup_broken_pos.py
ONE-TIME cleanup: the first 18 "AREKS-HIST-PO-*" purchase orders were
created while a stale leftover currency.rate row (base demo seed data
dated 2010-01-01) was still shadowing our real TRY/USD/EUR rates for
every historical (backdated) date - see the fix in 02_companies.py.
Result: their vendor bills and stock valuation used a wildly wrong
EUR/USD->TRY conversion.

This script properly reverses each of the 18 POs using only sanctioned
Odoo mechanisms (no raw SQL, no hand-editing of valuation/accounting
records):
  1. Unpost + delete the (wrong) vendor bill.
  2. For the 3 POs that got a landed cost: Odoo refuses to cancel a
     validated landed cost ("create negative landed costs to reverse
     them" - its own error message) - so we create an equal-and-opposite
     negative-cost landed cost on the same picking.
  3. Create a proper Return for the receipt picking (reverses the
     stock valuation to net zero) and validate it.
  4. Cancel + delete the now-empty PO.

This leaves harmless zero-net, no-value "receipt + return" picking
pairs in Inventory > Transfers history (done pickings cannot be
deleted outright - Odoo's own guidance for this exact situation is
"change the done quantity instead", which is what the return does).
After this, 10a_purchases.py is re-run to regenerate the same 18 POs
correctly.

This script is NOT idempotent by design (it's a one-time fix for a
specific mistake) - it only acts on POs whose partner_ref matches the
AREKS-HIST-PO-* marker and are still in a non-cancelled state.
"""

print("=" * 70)
print("10a_cleanup_broken_pos.py starting")
print("=" * 70)

PO = env['purchase.order'].sudo()
AccountMove = env['account.move'].sudo()
LandedCost = env['stock.landed.cost'].sudo()

pos = PO.search([('partner_ref', 'like', 'AREKS-HIST-PO-'), ('state', '!=', 'cancel')])
print(f"  found {len(pos)} POs to reverse")

for po in pos:
    marker = po.partner_ref
    print(f"  --- reversing {marker} ({po.name}) ---")

    # 1. landed costs on this PO's pickings -> negative reversal
    lcs = LandedCost.search([('picking_ids', 'in', po.picking_ids.ids), ('state', '=', 'done')])
    for lc in lcs:
        reverse_lines = [
            (0, 0, {
                'product_id': line.product_id.id,
                'price_unit': -line.price_unit,
                'split_method': line.split_method,
            })
            for line in lc.cost_lines
        ]
        reverse_lc = LandedCost.with_company(po.company_id).create({
            'picking_ids': [(6, 0, lc.picking_ids.ids)],
            'company_id': po.company_id.id,
            'date': lc.date,
            'cost_lines': reverse_lines,
        })
        reverse_lc.compute_landed_cost()
        reverse_lc.button_validate()
        print(f"    [OK] reversed landed cost {lc.id} via negative landed cost {reverse_lc.id}")

    # 2. vendor bill -> draft + delete
    bills = po.invoice_ids
    if bills:
        bills.button_draft()
        bills.unlink()
        print(f"    [OK] removed {len(bills)} vendor bill(s)")

    # 3. receipt picking(s) -> proper return, validated
    for picking in po.picking_ids:
        if picking.state != 'done':
            continue
        orig_qty_by_product = {m.product_id.id: m.product_uom_qty for m in picking.move_ids}
        new_picking = picking._create_return()
        for mv in new_picking.move_ids:
            mv.product_uom_qty = orig_qty_by_product.get(mv.product_id.id, mv.product_uom_qty)
        new_picking.action_confirm()
        new_picking.action_assign()
        for mv in new_picking.move_ids:
            mv.picked = True
            for ml in mv.move_line_ids:
                ml.quantity = mv.product_uom_qty
        new_picking.button_validate()
        print(f"    [OK] returned picking {picking.name} via {new_picking.name}")

    # 4. cancel + delete the PO
    po.button_cancel()
    po.unlink()
    print(f"    [OK] cancelled and deleted {marker}")
    env.cr.commit()

print("-" * 70)
remaining = PO.search([('partner_ref', 'like', 'AREKS-HIST-PO-')])
print(f"SUMMARY: remaining AREKS-HIST-PO-* records: {len(remaining)} (expected 0)")
print("=" * 70)
print("10a_cleanup_broken_pos.py done")
print("=" * 70)
