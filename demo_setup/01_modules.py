"""
01_modules.py
Install all modules required for the Areks Group demo, one at a time,
committing after each successful install. Also activates Turkish (tr_TR)
and English (en_US) languages.

Idempotent: re-running skips modules already in state 'installed'.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/01_modules.py
"""

Module = env['ir.module.module'].sudo()

MODULES = [
    ('sale_management', 'Satis'),
    ('crm', 'CRM'),
    ('purchase', 'Satinalma'),
    ('purchase_requisition', 'Satinalma alternatifleri / call for tenders'),
    ('stock', 'Envanter'),
    ('stock_landed_costs', 'Landed Costs'),
    ('stock_dropshipping', 'Dropshipping'),
    ('product_expiry', 'Lot / son kullanma tarihi'),
    ('mrp', 'Uretim'),
    ('mrp_plm', 'PLM'),
    ('quality_control', 'Quality Control'),
    ('mrp_mps', 'MPS'),
    ('account_accountant', 'Muhasebe'),
    ('l10n_tr', 'Turkiye lokalizasyonu'),
    ('sale_purchase_inter_company_rules', 'Inter-company rules (sale/purchase sync)'),
    ('website', 'Website'),
    ('website_sale', 'eCommerce'),
    ('web_studio', 'Studio'),
    ('spreadsheet_dashboard', 'Spreadsheet Dashboard'),
    ('approvals', 'Approvals'),
]

print("=" * 70)
print("01_modules.py starting")
print("=" * 70)

results = []
stop_error = None

for name, label in MODULES:
    mod = Module.search([('name', '=', name)], limit=1)
    if not mod:
        print(f"  [FATAL] module '{name}' not found in ir.module.module")
        stop_error = (name, "module not found")
        break
    if mod.state == 'installed':
        print(f"  [SKIP] {name} ({label}) already installed")
        results.append((name, 'already_installed'))
        continue
    try:
        print(f"  [INSTALLING] {name} ({label}) ...")
        mod.button_immediate_install()
        env.cr.commit()
        mod_check = Module.search([('name', '=', name)], limit=1)
        print(f"  [OK] {name} -> state={mod_check.state}")
        results.append((name, mod_check.state))
    except Exception as e:
        env.cr.rollback()
        import traceback
        print(f"  [ERROR] installing {name} failed, rolled back:")
        traceback.print_exc()
        stop_error = (name, str(e))
        break

print("-" * 70)
print("Module install results:")
for name, state in results:
    print(f"   {name:40s} {state}")
if stop_error:
    print(f"STOPPED at module '{stop_error[0]}': {stop_error[1]}")
print("-" * 70)

if not stop_error:
    # --- Languages: activate Turkish + English ---
    Lang = env['res.lang'].sudo()
    lang_results = []
    for code in ('en_US', 'tr_TR'):
        existing = Lang.search([('code', '=', code)], limit=1)
        if existing and existing.active:
            print(f"  [SKIP] language {code} already active")
            lang_results.append((code, 'already_active'))
            continue
        try:
            Lang._activate_lang(code)
            env.cr.commit()
            print(f"  [OK] language activated: {code}")
            lang_results.append((code, 'activated'))
        except Exception as e:
            env.cr.rollback()
            import traceback
            print(f"  [ERROR] activating language {code} failed:")
            traceback.print_exc()
            stop_error = (f"lang:{code}", str(e))
            break

    print("-" * 70)
    print("Language results:", lang_results)

print("=" * 70)
print("01_modules.py done" if not stop_error else "01_modules.py STOPPED WITH ERROR")
print("=" * 70)
