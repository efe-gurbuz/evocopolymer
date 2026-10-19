"""
11_live_demo_drafts.py
Live-demo starting points - DRAFTS ONLY, never confirmed/approved (per
task instructions - these are meant to be clicked through live):

  1. Areks: RFQ for R4110 20,000 kg, with 2 linked alternative RFQs to
     the other 2 vendors (purchase_alternative module), each priced
     from their supplierinfo - total comfortably exceeds the 250,000
     TRY two-step-approval threshold.
  2. Evoco: draft SO to Trakya Panel Yapı for EVO-RP 210, 10,000 kg
     (exceeds on-hand stock, to trigger an MTO/MO suggestion once
     confirmed live).
  3. Areks: draft SO to Yıldız Sünger for N-Pentane, dropship route
     pre-selected on the line.

Idempotent via unique partner_ref / client_order_ref markers.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/11_live_demo_drafts.py
"""

print("=" * 70)
print("11_live_demo_drafts.py starting")
print("=" * 70)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
Product = env['product.template'].sudo()
Partner = env['res.partner'].sudo()
marx = env['res.users'].sudo().search([('login', '=', 'marx@areksgroup.demo')], limit=1)
assert marx, "Marx not found - run 09_users.py first"

# -----------------------------------------------------------------------
# 1. Areks: R4110 20,000 kg RFQ with 3 vendor alternatives - created by
# Marx (audit tur 2, point 2), ICIS price left empty, correct supplierinfo
# -based prices (now fixed, see 08_contacts.py).
# -----------------------------------------------------------------------
MARKER_1 = "LIVE-DEMO-RFQ-R4110"
PO = env['purchase.order'].sudo().with_user(marx).with_company(areks)
existing = PO.search([('partner_ref', '=', MARKER_1), ('company_id', '=', areks.id)], limit=1)
if existing:
    print(f"  [SKIP] live-demo R4110 RFQ already exists ({existing.name})")
else:
    r4110 = Product.search([('name', '=', 'R4110')], limit=1)
    # NOTE (bug found & fixed): r4110.seller_ids now also includes the
    # Areks-as-vendor-for-Evoco supplierinfo row added in
    # 05b_routes_reorder.py (audit point 3/6, company_id=evoco,
    # sequence=0) - Areks buying R4110 FROM ITSELF makes no sense for
    # this external-vendor RFQ, so it must be excluded here.
    sellers = {s.partner_id: s for s in r4110.seller_ids if s.partner_id != areks.partner_id}
    assert len(sellers) >= 3, "expected at least 3 external vendors for R4110"
    vendors = list(sellers.keys())

    main_vendor = vendors[0]
    main_price = sellers[main_vendor].price
    po1 = PO.create({
        'partner_id': main_vendor.id,
        'company_id': areks.id,
        # NOTE (bug found & fixed, same root cause as 10a_purchases.py):
        # a raw ORM create() never fires the partner_id onchange that
        # normally sets currency_id to the vendor's own currency.
        'currency_id': main_vendor.property_purchase_currency_id.id,
        'partner_ref': MARKER_1,
        'order_line': [(0, 0, {
            'product_id': r4110.product_variant_id.id,
            'product_qty': 20000,
            'price_unit': main_price,
            # x_icis_price intentionally left empty (audit tur 2, point 2)
        })],
    })
    print(f"  [OK] original RFQ created: {po1.name} -> {main_vendor.name} "
          f"({po1.amount_total} {po1.currency_id.name})")

    other_vendors = vendors[1:3]
    wiz = env['purchase.alternative.create'].sudo().with_user(marx).create({
        'origin_po_id': po1.id,
        'partner_ids': [(6, 0, [v.id for v in other_vendors])],
        'copy_products': True,
    })
    res = wiz.with_user(marx).action_create_alternative()
    alt_pos = env['purchase.order'].sudo().browse(res['domain'][0][2]) if 'domain' in res else env['purchase.order'].sudo().browse(res['res_id'])
    for alt in alt_pos:
        alt.partner_ref = f"{MARKER_1}-ALT-{alt.partner_id.id}"
        v = alt.partner_id
        if v in sellers:
            alt.order_line.write({'price_unit': sellers[v].price})
        print(f"  [OK] alternative RFQ created: {alt.name} -> {v.name} "
              f"({alt.amount_total} {alt.currency_id.name})")

    print(f"  [INFO] PO {po1.name} alternative_po_ids: {po1.alternative_po_ids.mapped('name')}")
    print("  [INFO] all left in draft - NOT confirmed, per instructions")
    env.cr.commit()

# -----------------------------------------------------------------------
# 2. Evoco: draft SO, EVO-RP 210 x 10,000 kg (exceeds stock) to Trakya
# -----------------------------------------------------------------------
MARKER_2 = "LIVE-DEMO-SO-RP210"
SO = env['sale.order'].sudo().with_company(evoco)
existing = SO.search([('client_order_ref', '=', MARKER_2), ('company_id', '=', evoco.id)], limit=1)
if existing:
    print(f"  [SKIP] live-demo Evoco SO already exists ({existing.name})")
else:
    rp210 = Product.search([('default_code', '=', 'EVO-RP 210')], limit=1)
    trakya = Partner.search([('name', '=', 'Trakya Panel Yapı A.Ş.')], limit=1)
    on_hand = rp210.with_company(evoco).qty_available
    so2 = SO.create({
        'partner_id': trakya.id,
        'company_id': evoco.id,
        'client_order_ref': MARKER_2,
        'order_line': [(0, 0, {
            'product_id': rp210.product_variant_id.id,
            'product_uom_qty': 10000,
            'price_unit': rp210.list_price,
        })],
    })
    print(f"  [OK] draft SO created: {so2.name} (state={so2.state}), "
          f"RP210 on-hand={on_hand}kg vs ordered=10000kg "
          f"({'insufficient - good' if on_hand < 10000 else 'WARNING: stock is sufficient, MTO will not trigger'})")
    env.cr.commit()

# -----------------------------------------------------------------------
# 3. Areks: draft SO, N-Pentane, dropship route pre-selected
# -----------------------------------------------------------------------
MARKER_3 = "LIVE-DEMO-SO-DROPSHIP"
SO3 = env['sale.order'].sudo().with_company(areks)
existing = SO3.search([('client_order_ref', '=', MARKER_3), ('company_id', '=', areks.id)], limit=1)
if existing:
    print(f"  [SKIP] live-demo Areks dropship SO already exists ({existing.name})")
else:
    npentane = Product.search([('name', '=', 'N-Pentane')], limit=1)
    yildiz = Partner.search([('name', '=', 'Yıldız Sünger San. A.Ş.')], limit=1)
    dropship_route = env['stock.route'].sudo().search([('name', '=', 'Dropship')], limit=1)
    so3 = SO3.create({
        'partner_id': yildiz.id,
        'company_id': areks.id,
        'client_order_ref': MARKER_3,
        'order_line': [(0, 0, {
            'product_id': npentane.product_variant_id.id,
            'product_uom_qty': 1000,  # audit point 11: live-demo dropship must be 1000kg
            'price_unit': npentane.list_price,
            'route_ids': [(6, 0, [dropship_route.id])],
        })],
    })
    print(f"  [OK] draft dropship SO created: {so3.name} (state={so3.state})")
    env.cr.commit()

print("=" * 70)
print("11_live_demo_drafts.py done")
print("=" * 70)
