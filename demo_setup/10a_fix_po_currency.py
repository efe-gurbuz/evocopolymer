"""
10a_fix_po_currency.py
One-time repair for a bug found in the AREKS-HIST-PO-* historical
purchases (10a_purchases.py): purchase.order.currency_id only ever
defaults to the vendor's own currency via an ONCHANGE on partner_id - a
raw ORM .create() (as used by the demo-data script) never fires that
onchange, so every PO silently got the company's currency (TRY)
regardless of vendor, while price_unit was still computed in the
VENDOR's own currency - understating every EUR/USD vendor's bill by the
TRY exchange factor (~34-37x).

For each affected (currency_id != vendor's own currency) PO:
  1. Reset its posted vendor bill to draft and delete it (ORM-safe -
     only possible because nothing is paid/reconciled yet).
  2. Correct the PO's own currency_id (price_unit values are untouched -
     they were always meant to be read in the vendor's currency, so the
     PO's total is numerically unchanged, only correctly labelled now).
  3. Regenerate and re-post the vendor bill, same invoice_date as before.
The receipt/lots/landed-costs side is untouched - genuinely unaffected,
since those don't carry a vendor-currency amount.

Idempotent: only acts on POs where currency_id doesn't match the
vendor's property_purchase_currency_id.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/10a_fix_po_currency.py
"""

print("=" * 70)
print("10a_fix_po_currency.py starting")
print("=" * 70)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
PO = env['purchase.order'].sudo().with_company(areks)

pos = PO.search([('partner_ref', 'like', 'AREKS-HIST-PO-%'), ('company_id', '=', areks.id)])
fixed = 0
skipped = 0
for po in pos:
    vendor_currency = po.partner_id.property_purchase_currency_id
    if po.currency_id == vendor_currency:
        skipped += 1
        continue

    old_bill = po.invoice_ids
    if old_bill:
        if old_bill.state == 'posted':
            old_bill.button_draft()
        old_bill.unlink()

    po.currency_id = vendor_currency.id

    bill_state = 'n/a'
    try:
        action = po.action_create_invoice()
        new_bill = env['account.move'].sudo().browse(action['res_id'])
        new_bill.invoice_date = (po.date_approve.date() if po.date_approve else po.date_order.date())
        new_bill.action_post()
        bill_state = f"{new_bill.name} ({new_bill.state})"
    except Exception as e:
        bill_state = f"ERROR: {e}"

    env.cr.commit()
    fixed += 1
    print(f"  [FIX] {po.partner_ref}: {po.name} -> currency={po.currency_id.name}, "
          f"total={po.amount_total}, new bill={bill_state}")

print("-" * 70)
print(f"SUMMARY: fixed={fixed} already_correct={skipped}")
print("=" * 70)
print("10a_fix_po_currency.py done")
print("=" * 70)
