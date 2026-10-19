"""
03_categories.py
Product category tree + AVCO/automated valuation (per company, since
property_cost_method/property_valuation are company-dependent) + FEFO
removal strategy on raw-material categories.

Idempotent: search-by-name-and-parent before create.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/03_categories.py
"""

print("=" * 70)
print("03_categories.py starting")
print("=" * 70)

Category = env['product.category'].sudo()
Removal = env['product.removal'].sudo()
areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
companies = (areks, evoco)

fefo = Removal.search([('method', '=', 'fefo')], limit=1)
assert fefo, "FEFO removal strategy (product.removal) not found"


def get_or_create_category(name, parent):
    domain = [('name', '=', name), ('parent_id', '=', parent.id if parent else False)]
    cat = Category.search(domain, limit=1)
    if cat:
        print(f"  [SKIP] category exists: {cat.display_name}")
        return cat
    cat = Category.create({'name': name, 'parent_id': parent.id if parent else False})
    print(f"  [OK] category created: {cat.display_name}")
    return cat


def set_valuation(category, stocked, fefo_strategy=False):
    """Set AVCO + perpetual valuation (per company) for stocked categories."""
    if stocked:
        for company in companies:
            cat_c = category.with_company(company)
            vals = {}
            if cat_c.property_cost_method != 'average':
                vals['property_cost_method'] = 'average'
            if cat_c.property_valuation != 'real_time':
                vals['property_valuation'] = 'real_time'
            if vals:
                cat_c.write(vals)
                print(f"    [OK] {category.name} / {company.name}: cost_method=average, valuation=real_time")
            else:
                print(f"    [SKIP] {category.name} / {company.name}: already AVCO + real_time")
    if fefo_strategy:
        if category.removal_strategy_id != fefo:
            category.removal_strategy_id = fefo.id
            print(f"    [OK] {category.name}: removal strategy set to FEFO")
        else:
            print(f"    [SKIP] {category.name}: removal strategy already FEFO")


# --- Hammadde / Polioller, İzosiyanatlar, Yardımcı Kimyasallar (stocked + FEFO) ---
hammadde = get_or_create_category('Hammadde', False)
polioller = get_or_create_category('Polioller', hammadde)
izosiyanatlar = get_or_create_category('İzosiyanatlar', hammadde)
yardimci = get_or_create_category('Yardımcı Kimyasallar', hammadde)
# audit tur 2, point 5: the top-level "Hammadde"/"Mamul" categories
# themselves were left at the plain default (periodic/standard) - only
# their leaf children got AVCO/real_time. Fix the top-level ones too.
set_valuation(hammadde, stocked=True, fefo_strategy=False)
for cat in (polioller, izosiyanatlar, yardimci):
    set_valuation(cat, stocked=True, fefo_strategy=True)

# --- Yarı Mamul (stocked, no FEFO) ---
yari_mamul = get_or_create_category('Yarı Mamul', False)
set_valuation(yari_mamul, stocked=True, fefo_strategy=False)

# --- Mamul / PU Sistemleri (stocked, no FEFO) ---
mamul = get_or_create_category('Mamul', False)
pu_sistemleri = get_or_create_category('PU Sistemleri', mamul)
set_valuation(mamul, stocked=True, fefo_strategy=False)
set_valuation(pu_sistemleri, stocked=True, fefo_strategy=False)

# --- Hizmet / İthalat Masrafları (service, not stocked) ---
hizmet = get_or_create_category('Hizmet', False)
ithalat_masraflari = get_or_create_category('İthalat Masrafları', hizmet)
# no valuation needed for service-only category

env.cr.commit()

print("-" * 70)
print("SUMMARY categories:")
for cat in (hammadde, polioller, izosiyanatlar, yardimci, yari_mamul, mamul, pu_sistemleri, hizmet, ithalat_masraflari):
    print(f"   id={cat.id:5d}  {cat.display_name}")
print("=" * 70)
print("03_categories.py done")
print("=" * 70)
