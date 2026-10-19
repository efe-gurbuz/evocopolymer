"""
10b_intercompany.py
Inter-company: 5 raw-material sales from Areks to Evoco. Each Areks SO,
once confirmed, auto-generates a (already-approved, per our company
settings) PO on Evoco's side; we then receive it there too.

Idempotent via a unique client_order_ref marker per line.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/10b_intercompany.py
"""

import datetime
import hashlib

print("=" * 70)
print("10b_intercompany.py starting")
print("=" * 70)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
Product = env['product.template'].sudo()
SO = env['sale.order'].sudo().with_company(areks)
Lot = env['stock.lot'].sudo()

today = datetime.date.today()
ark = env['stock.warehouse'].sudo().search([('company_id', '=', areks.id)], limit=1)

RAW_MATERIALS = ["R4110", "Adipik Asit", "Dietilen Glikol (DEG)", "Yanmazlık TCPP", "Cyclopentane"]

def ensure_invoiced(so, backdate, i):
    """ audit point 4: self-healing - a SO created by an earlier run
    (before invoicing was added here) must still get invoiced now, with
    Evoco's vendor bill auto-generated via intercompany_generate_bills_refund. """
    existing_inv = so.invoice_ids.filtered(lambda m: m.state == 'posted')
    if existing_inv:
        inv = existing_inv[0]
    else:
        try:
            inv = so._create_invoices()
            inv.invoice_date = backdate
            inv.action_post()
        except Exception as e:
            print(f"    [WARN] could not invoice {so.name}: {e}")
            return
    evk_bill = env['account.move'].sudo().search([
        ('move_type', '=', 'in_invoice'),
        ('company_id', '=', evoco.id),
        ('auto_invoice_id', '=', inv.id),
    ], limit=1)
    print(f"    [OK] {so.name} invoice={inv.name} ({inv.state}), "
          f"Evoco auto-bill={evk_bill.name if evk_bill else 'NOT FOUND'}"
          f"{' (' + evk_bill.state + ')' if evk_bill else ''}")
    env.cr.commit()


created = 0
skipped = 0
for i, name in enumerate(RAW_MATERIALS):
    marker = f"AREKS-IC-{i:02d}"
    # audit-rebuild fix: a marker match alone can hit a leftover SO
    # still sitting under the OLD (now archived/renamed) company id.
    existing = SO.search([('client_order_ref', '=', marker), ('company_id', '=', areks.id)], limit=1)
    if existing:
        skipped += 1
        print(f"  [SKIP] {marker} already exists ({existing.name}) - checking invoice/bill...")
        existing_backdate = existing.date_order.date() if existing.date_order else today
        ensure_invoiced(existing, existing_backdate, i)
        continue

    prod = Product.search([('name', '=', name)], limit=1)
    variant = prod.product_variant_id
    days_ago = 100 - i * 15
    backdate = today - datetime.timedelta(days=days_ago)
    qty = 1000 + i * 200

    # make sure Areks has enough on-hand stock to deliver (top up if needed)
    on_hand = variant.with_company(areks).qty_available
    if on_hand < qty:
        need = qty - on_hand + 500
        # audit point 1: lots are shared (company_id=False), same as the
        # product they're created for - never pass company_id explicitly.
        lot = Lot.create({'name': f"ARK-IC-STOCK-{i:02d}", 'product_id': variant.id})
        env['stock.quant'].with_company(areks)._update_available_quantity(variant, ark.lot_stock_id, need, lot_id=lot)
        print(f"    [OK] topped up {need} kg of {name} at Areks for the inter-company sale")

    so = SO.create({
        'partner_id': evoco.partner_id.id,
        'company_id': areks.id,
        'date_order': backdate,
        'client_order_ref': marker,
        'order_line': [(0, 0, {
            'product_id': variant.id,
            'product_uom_qty': qty,
            'price_unit': round(prod.list_price, 2),
        })],
    })
    so.action_confirm()

    # deliver on Areks side
    picking = so.picking_ids.filtered(lambda p: p.state != 'done')
    if picking:
        for p in picking:
            p.action_assign()
            for mv in p.move_ids:
                mv.picked = True
                for ml in mv.move_line_ids:
                    if not ml.lot_id:
                        lot = Lot.create({'name': f"ARK-IC-OUT-{i:02d}", 'product_id': mv.product_id.id})
                        ml.lot_id = lot.id
                    ml.quantity = ml.quantity or mv.product_uom_qty
            p.move_ids.write({'date': backdate})
            p.button_validate()

    # auto-created PO on Evoco side
    auto_po = env['purchase.order'].sudo().search([
        ('partner_id', '=', areks.partner_id.id),
        ('company_id', '=', evoco.id),
        ('auto_sale_order_id', '=', so.id),
    ], limit=1)
    po_state = auto_po.state if auto_po else 'NOT FOUND'
    if auto_po and auto_po.state == 'purchase':
        evk_picking = auto_po.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        for p in evk_picking:
            p.action_assign()
            for mv in p.move_ids:
                mv.picked = True
                for ml_idx, ml in enumerate(mv.move_line_ids):
                    # audit point 1 (root-cause fix): lots are shared
                    # (company_id=False), exactly like the shared raw
                    # material products they're created for. With the
                    # old (wrong) company-scoped lots, action_assign()'s
                    # auto-fill of the ORIGIN (Areks) lot used to fail
                    # Odoo's cross-company consistency check at validate
                    # time, which an earlier version of this script
                    # "fixed" by forging a second, renamed Evoco-only lot
                    # for the same physical batch - that was itself a
                    # symptom of the root bug, not a real fix, and broke
                    # lot traceability across the inter-company chain.
                    # Now that lots carry no company_id at all, the SAME
                    # lot naturally flows Areks -> Evoco with no mismatch;
                    # only create one if truly missing.
                    if not ml.lot_id:
                        lot = Lot.create({
                            'name': f"EVK-IC-IN-{i:02d}-{ml_idx:02d}",
                            'product_id': mv.product_id.id,
                        })
                        ml.lot_id = lot.id
                    ml.quantity = ml.quantity or mv.product_uom_qty
            p.move_ids.write({'date': backdate})
            p.button_validate()
            # audit validation flow 2: Evoco's receipt quality check
            # ("Yoğunluk ölçümü" quality point, hammadde categories /
            # incoming) is non-blocking so button_validate() succeeds
            # even with it still pending - explicitly pass it so the
            # flow is genuinely complete end-to-end.
            for check in env['quality.check'].sudo().search([
                ('picking_id', 'in', evk_picking.ids), ('quality_state', '=', 'none'),
            ]):
                if check.test_type == 'measure':
                    check.measure = 1.1
                    check.do_measure()
                else:
                    check.do_pass()

    # audit point 4: intercompany_generate_bills_refund=True on both
    # companies (set in 02_companies.py) - posting the Areks customer
    # invoice must auto-generate Evoco's vendor bill. Invoice every
    # historical inter-company sale, not just deliver it.
    env.cr.commit()
    created += 1
    print(f"  [OK] {marker}: {name} x{qty}kg, Areks SO={so.name} ({so.state}), "
          f"Evoco PO={auto_po.name if auto_po else None} ({po_state})")
    ensure_invoiced(so, backdate, i)

print("-" * 70)
print(f"SUMMARY: created={created} skipped(existing)={skipped}")
print("=" * 70)
print("10b_intercompany.py done")
print("=" * 70)
