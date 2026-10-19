"""
10d_sales.py
Historical customer sales (last ~5 months):
  - Evoco: 6 SOs to its 3 customers, delivered from stock, invoiced.
  - Areks: 6 SOs to its 3 customers, 2 of them dropship-routed,
    delivered (or dropship-received+shipped), invoiced.
  - Evoco -> Areks: 2 sales of the EVO-RP 210 SET kit ("Rigid Polyol
    Sistemler"), which explodes into its phantom-BOM components at
    delivery.

Idempotent via a unique client_order_ref marker per order.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/10d_sales.py
"""

import datetime

print("=" * 70)
print("10d_sales.py starting")
print("=" * 70)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
Product = env['product.template'].sudo()
Partner = env['res.partner'].sudo()
Lot = env['stock.lot'].sudo()
Quant = env['stock.quant'].sudo()
AccountMove = env['account.move'].sudo()
today = datetime.date.today()


def company_on_hand(variant, company):
    wh = env['stock.warehouse'].sudo().search([('company_id', '=', company.id)], limit=1)
    quants = env['stock.quant'].sudo().search([
        ('product_id', '=', variant.id),
        ('location_id', 'child_of', wh.lot_stock_id.id),
    ])
    return sum(quants.mapped('quantity'))


_topup_counter = {'n': 0}


def ensure_stock(name, qty_needed, company, buffer=1.1):
    prod = Product.search([('name', '=', name)], limit=1)
    variant = prod.product_variant_id
    have = company_on_hand(variant, company)
    if have >= qty_needed:
        return
    wh = env['stock.warehouse'].sudo().search([('company_id', '=', company.id)], limit=1)
    need = round((qty_needed - have) * buffer + 10, 2)
    _topup_counter['n'] += 1
    # NOTE (bug found & fixed): since lots are correctly shared
    # (company_id=False per audit point 1), the lot name+product
    # combination must be unique GLOBALLY, not per-company - a fixed
    # "{company}-OPEN-{product_id}" name collided on the second top-up
    # of the same product. Add a monotonic counter.
    lot = Lot.create({'name': f"{company.name[:4].upper()}-OPEN-{prod.id}-{_topup_counter['n']:03d}",
                       'product_id': variant.id})
    Quant.with_company(company)._update_available_quantity(variant, wh.lot_stock_id, need, lot_id=lot)
    print(f"    [OK] topped up {need} kg {name} at {company.name}")


def pass_quality_checks(mo):
    for check in mo.check_ids:
        if check.quality_state != 'none':
            continue
        if check.test_type == 'measure':
            check.measure = 14  # within configured tolerance (Krem suresi 8-20sn)
            check.do_measure()
        elif check.test_type == 'passfail':
            check.do_pass()
        else:
            check.do_pass()


def complete_pending_mos(company, backdate):
    """ audit point 3/11: EVO-RP 210 and 5 other Evoco finished goods (+
    EVO-PMX R) are now on the MTO route - confirming a customer SO no
    longer reserves from stock directly, it auto-creates a (possibly
    multi-level, e.g. EVO-RP 210 -> EVO-PMX R) chain of mrp.production
    records that must actually be PRODUCED before the delivery has
    anything to ship. Process whatever is pending, bottom-up, topping up
    pure raw materials reactively exactly like 10c_manufacturing.py does,
    repeating until the chain is fully resolved (handles multi-level BOMs). """
    Production = env['mrp.production'].sudo().with_company(company)
    wh = env['stock.warehouse'].sudo().search([('company_id', '=', company.id)], limit=1)
    for _ in range(10):  # chain depth safety cap
        pending = Production.search([
            ('company_id', '=', company.id), ('state', 'not in', ('done', 'cancel')),
        ])
        if not pending:
            break
        for mo in pending:
            for line in mo.move_raw_ids:
                needed = line.product_uom_qty
                have = company_on_hand(line.product_id, company)
                if have < needed:
                    ensure_stock(line.product_id.name, needed, company)
            mo.action_assign()
            pass_quality_checks(mo)
            if not mo.lot_producing_ids and mo.product_id.tracking != 'none':
                out_lot = Lot.create({'name': f"{company.name[:4].upper()}-MTO-{mo.id}",
                                       'product_id': mo.product_id.id})
                mo.lot_producing_ids = [(6, 0, [out_lot.id])]
            mo.qty_producing = mo.product_qty
            mo.move_raw_ids.write({'picked': True, 'date': backdate})
            mo.move_finished_ids.write({'date': backdate})
            res = mo.button_mark_done()
            if isinstance(res, dict) and res.get('res_model') == 'mrp.consumption.warning':
                mo.with_context(skip_consumption=True).button_mark_done()
            print(f"    [OK] auto-MTO MO completed: {mo.name} ({mo.product_id.name} x{mo.product_qty})")
    env.cr.commit()


def deliver_picking(picking, backdate, company):
    picking.action_assign()
    for mv in picking.move_ids:
        mv.picked = True
        for ml in mv.move_line_ids:
            if mv.product_id.tracking != 'none' and not ml.lot_id:
                # audit point 1: never set company_id on a lot.
                lot = Lot.create({
                    'name': f"{company.name[:4].upper()}-SALE-{mv.id}",
                    'product_id': mv.product_id.id,
                })
                ml.lot_id = lot.id
            ml.quantity = ml.quantity or mv.product_uom_qty
    picking.move_ids.write({'date': backdate})
    picking.button_validate()


def invoice_and_post(so, backdate):
    inv = so._create_invoices()
    inv.invoice_date = backdate
    inv.action_post()
    return inv


def run_so(marker, company, partner, lines, backdate, dropship=False):
    SO = env['sale.order'].sudo().with_company(company)
    # audit-rebuild fix: a marker match alone can hit a leftover SO
    # still sitting under the OLD (now archived/renamed) company id.
    existing = SO.search([('client_order_ref', '=', marker), ('company_id', '=', company.id)], limit=1)
    if existing:
        print(f"  [SKIP] {marker} already exists ({existing.name})")
        return existing

    dropship_route = env['stock.route'].sudo().search([('name', '=', 'Dropship')], limit=1) if dropship else None
    order_lines = []
    for name, qty, price in lines:
        prod = Product.search([('name', '=', name)], limit=1)
        if not dropship and prod.is_storable:
            # kits (is_storable=False, phantom BOM) never hold their own
            # stock - Odoo refuses direct quant updates on them ("update
            # the components quantity instead of ... the kit product").
            ensure_stock(name, qty, company)
        line_vals = {
            'product_id': prod.product_variant_id.id,
            'product_uom_qty': qty,
            'price_unit': price,
        }
        if dropship:
            line_vals['route_ids'] = [(6, 0, [dropship_route.id])]
        order_lines.append((0, 0, line_vals))

    so = SO.create({
        'partner_id': partner.id,
        'company_id': company.id,
        'date_order': backdate,
        'client_order_ref': marker,
        'order_line': order_lines,
    })
    so.action_confirm()

    if not dropship:
        # audit point 3/11: the finished-goods products are on the MTO
        # route now - resolve any auto-generated production chain before
        # attempting to deliver (no-op for Areks, whose raw materials
        # aren't BOM/MTO products).
        complete_pending_mos(company, backdate)

    if dropship:
        # dropship: a PO is auto-created to the vendor; confirm + receive
        # it (receipt ships straight to the customer)
        po = env['purchase.order'].sudo().search(
            [('origin', 'like', so.name), ('company_id', '=', company.id)], limit=1)
        if po and po.state == 'draft':
            po.button_confirm()
            if po.state == 'to approve':
                po.button_approve()
        if po:
            for p in po.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
                deliver_picking(p, backdate, company)
    else:
        for p in so.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
            deliver_picking(p, backdate, company)

    bill_state = 'n/a'
    try:
        inv = invoice_and_post(so, backdate)
        bill_state = inv.state
    except Exception as e:
        bill_state = f"ERROR: {e}"

    env.cr.commit()
    print(f"  [OK] {marker}: {so.name} ({so.state}) partner={partner.name} "
          f"total={so.amount_total} {so.currency_id.name} invoice={bill_state}")
    return so


# -----------------------------------------------------------------------
# Evoco: 6 customer SOs from stock, invoiced
# -----------------------------------------------------------------------
trakya = Partner.search([('name', '=', 'Trakya Panel Yapı A.Ş.')], limit=1)
kuzey = Partner.search([('name', '=', 'Kuzey Soğutma Sistemleri A.Ş.')], limit=1)
konfor = Partner.search([('name', '=', 'Konfor Yatak San. Ltd.')], limit=1)

EVOCO_SALES = [
    ("EVOCO-SALE-00", trakya, [("Rijit Panel Sistemi – Komponent A", 1500, 145.0)], 95),
    ("EVOCO-SALE-01", kuzey, [("Soğutma Sistemi – Komponent A", 400, 135.0)], 85),
    ("EVOCO-SALE-02", konfor, [("Semi-Rigid Sistem – Komponent A", 300, 130.0)], 75),
    ("EVOCO-SALE-03", trakya, [("Rijit Panel Sistemi – Komponent A", 2000, 145.0)], 60),
    ("EVOCO-SALE-04", kuzey, [("Sprey İzolasyon Sistemi – Komponent A", 350, 150.0)], 45),
    ("EVOCO-SALE-05", konfor, [("Esnek Köpük Sistemi – Komponent A", 400, 120.0)], 20),
]
for marker, partner, lines, days_ago in EVOCO_SALES:
    run_so(marker, evoco, partner, lines, today - datetime.timedelta(days=days_ago))

# -----------------------------------------------------------------------
# Areks: 6 customer SOs, 2 dropship
# -----------------------------------------------------------------------
yildiz = Partner.search([('name', '=', 'Yıldız Sünger San. A.Ş.')], limit=1)
ege = Partner.search([('name', '=', 'Ege Yalıtım Malzemeleri Ltd.')], limit=1)
balkan = Partner.search([('name', '=', 'Balkan Foam d.o.o.')], limit=1)

AREKS_SALES = [
    ("AREKS-SALE-00", yildiz, [("Konvansiyonel Şeffaf Polyol", 1000, 68.0)], 90, False),
    ("AREKS-SALE-01", ege, [("Semi-Rigid Poliol", 800, 71.0)], 80, False),
    ("AREKS-SALE-02", balkan, [("TDI", 600, 89.0)], 70, False),
    ("AREKS-SALE-03", yildiz, [("%25 Polimerik Polyol (POP)", 900, 79.0)], 50, False),
    ("AREKS-SALE-04", ege, [("N-Pentane", 500, 93.0)], 35, True),   # dropship
    ("AREKS-SALE-05", yildiz, [("Cyclopentane", 400, 97.0)], 15, True),  # dropship
]
for marker, partner, lines, days_ago, dropship in AREKS_SALES:
    run_so(marker, areks, partner, lines, today - datetime.timedelta(days=days_ago), dropship=dropship)

# -----------------------------------------------------------------------
# Evoco -> Areks: 2 sales of the EVO-RP 210 SET kit
# -----------------------------------------------------------------------
# make sure Evoco has enough Polimerik MDI on hand for the kit's
# phantom-BOM explosion (1100 kg per set)
evk = env['stock.warehouse'].sudo().search([('company_id', '=', evoco.id)], limit=1)
mdi = Product.search([('name', '=', 'Polimerik MDI')], limit=1).product_variant_id
mdi_have = sum(env['stock.quant'].sudo().search([
    ('product_id', '=', mdi.id), ('location_id', 'child_of', evk.lot_stock_id.id)]).mapped('quantity'))
mdi_needed = 2500.0
if mdi_have < mdi_needed:
    _n = env['stock.lot'].sudo().search_count([('name', 'like', 'EVK-KIT-MDI-OPEN')])
    # audit point 1: never set company_id on a lot.
    lot = Lot.create({'name': f'EVK-KIT-MDI-OPEN-{_n + 1:02d}', 'product_id': mdi.id})
    Quant.with_company(evoco)._update_available_quantity(mdi, evk.lot_stock_id, mdi_needed - mdi_have + 10, lot_id=lot)
    print(f"  [OK] topped up {mdi_needed - mdi_have + 10} kg Polimerik MDI at Evoco for kit sales")

KIT_SALES = [
    ("EVOCO-KIT-00", 50),
    ("EVOCO-KIT-01", 25),
]
for marker, days_ago in KIT_SALES:
    run_so(marker, evoco, areks.partner_id, [("Rijit Panel Sistemi A+B Seti", 1, 236795.0)],
           today - datetime.timedelta(days=days_ago))

print("-" * 70)
print(f"SUMMARY: Evoco SOs={env['sale.order'].sudo().search_count([('client_order_ref','like','EVOCO-SALE-%')])}, "
      f"Areks SOs={env['sale.order'].sudo().search_count([('client_order_ref','like','AREKS-SALE-%')])}, "
      f"Kit SOs={env['sale.order'].sudo().search_count([('client_order_ref','like','EVOCO-KIT-%')])}")
print("=" * 70)
print("10d_sales.py done")
print("=" * 70)
