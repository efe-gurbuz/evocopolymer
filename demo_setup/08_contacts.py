"""
08_contacts.py
Fictitious supplier and customer contacts for Areks Group, plus
product.supplierinfo price lists so each raw material has 2-3 vendors
at different prices, and each landed-cost service product has its
specialist vendor.

Idempotent: search by name before create.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/08_contacts.py
"""

import hashlib

print("=" * 70)
print("08_contacts.py starting")
print("=" * 70)

Partner = env['res.partner'].sudo()
Country = env['res.country'].sudo()
Currency = env['res.currency'].sudo().with_context(active_test=False)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
assert areks and evoco, "companies not found - run 02_companies.py first"

DE = Country.search([('code', '=', 'DE')], limit=1)
AE = Country.search([('code', '=', 'AE')], limit=1)
GB = Country.search([('code', '=', 'GB')], limit=1)
TR = Country.search([('code', '=', 'TR')], limit=1)
RS = Country.search([('code', '=', 'RS')], limit=1)
EUR = Currency.search([('name', '=', 'EUR')], limit=1)
USD = Currency.search([('name', '=', 'USD')], limit=1)
TRY = Currency.search([('name', '=', 'TRY')], limit=1)


def set_purchase_currency_everywhere(partner, currency_id):
    # NOTE (bug found & fixed): property_purchase_currency_id is a
    # company_dependent ("property") field - writing it under a plain
    # (no with_company) env stores the value keyed to WHATEVER
    # env.company happens to be at that moment (an odoo-bin shell
    # session's default is NOT guaranteed to be a real/current company -
    # it silently resolved to an ARCHIVED one here), so the property was
    # only ever set for that one company and read back as EMPTY under
    # Areks/Evoco's own with_company() context - exactly the gap that
    # made purchase.order.currency_id resolve wrong down the line. Set
    # it explicitly for both real companies that will ever purchase from
    # this vendor.
    for company in (areks, evoco):
        p_scoped = partner.with_company(company)
        if p_scoped.property_purchase_currency_id.id != currency_id:
            p_scoped.property_purchase_currency_id = currency_id


def get_or_create_partner(name, vals):
    currency = vals.pop('property_purchase_currency_id', None)
    existing = Partner.search([('name', '=', name)], limit=1)
    if existing:
        if currency:
            set_purchase_currency_everywhere(existing, currency)
        print(f"  [SKIP] partner exists: {name}")
        return existing
    # NOTE (found & fixed): is_company is a COMPUTED+stored field here
    # (partner.is_company = partner.commercial_partner_id == partner and
    # partner.has_vat) - writing True directly is silently discarded.
    # A partner only shows as "a company" once it has a valid VAT/tax id
    # (has_vat depends on `vat`), so every org-type contact below gets a
    # real (checksum-valid) vat in its vals - see VENDOR/CUSTOMER tables.
    vals = dict(vals, name=name, company_id=False)
    p = Partner.create(vals)
    if currency:
        set_purchase_currency_everywhere(p, currency)
    print(f"  [OK] partner created: {name} (id={p.id}) is_company={p.is_company}")
    return p


# -----------------------------------------------------------------------
# Suppliers
# -----------------------------------------------------------------------
nordpol = get_or_create_partner("Nordpol Chemie GmbH", {
    'country_id': DE.id, 'property_purchase_currency_id': EUR.id,
    'vat': 'DE123456788', 'email': 'sales@nordpolchemie.de', 'supplier_rank': 1,
    'city': 'Hamburg',
})
gulfstream = get_or_create_partner("Gulfstream Petrochem FZE", {
    'country_id': AE.id, 'property_purchase_currency_id': USD.id,
    'vat': '100234567800003', 'email': 'sales@gulfstreampetrochem.ae', 'supplier_rank': 1,
    'city': 'Dubai',
})
eastbridge = get_or_create_partner("Eastbridge Isocyanates Ltd.", {
    'country_id': GB.id, 'property_purchase_currency_id': USD.id,
    'vat': 'GB123456782', 'email': 'sales@eastbridge-iso.co.uk', 'supplier_rank': 1,
    'city': 'London',
})
anatolia = get_or_create_partner("Anatolia Specialty Chemicals A.Ş.", {
    'country_id': TR.id, 'property_purchase_currency_id': TRY.id,
    'vat': '1000000034', 'email': 'info@anatoliaspecialty.com.tr', 'supplier_rank': 1,
    'city': 'Kocaeli',
})
marmara_gumruk = get_or_create_partner("Marmara Gümrük Müşavirliği", {
    'country_id': TR.id, 'property_purchase_currency_id': TRY.id,
    'vat': '1000000041', 'email': 'info@marmaragumruk.com.tr', 'supplier_rank': 1,
    'city': 'İstanbul',
})
bogazici_lojistik = get_or_create_partner("Boğaziçi Lojistik", {
    'country_id': TR.id, 'property_purchase_currency_id': TRY.id,
    'vat': '1000000059', 'email': 'info@bogazicilojistik.com.tr', 'supplier_rank': 1,
    'city': 'İstanbul',
})

# -----------------------------------------------------------------------
# Areks customers
# -----------------------------------------------------------------------
yildiz_sunger = get_or_create_partner("Yıldız Sünger San. A.Ş.", {
    'country_id': TR.id, 'currency_id': TRY.id,
    'vat': '1000000067', 'email': 'info@yildizsunger.com.tr', 'customer_rank': 1, 'city': 'Kocaeli',
})
ege_yalitim = get_or_create_partner("Ege Yalıtım Malzemeleri Ltd.", {
    'country_id': TR.id, 'currency_id': TRY.id,
    'vat': '1000000075', 'email': 'info@egeyalitim.com.tr', 'customer_rank': 1, 'city': 'İzmir',
})
balkan_foam = get_or_create_partner("Balkan Foam d.o.o.", {
    'country_id': RS.id, 'currency_id': EUR.id,
    'vat': 'RS101134702', 'email': 'office@balkanfoam.rs', 'customer_rank': 1, 'city': 'Belgrade',
})

# -----------------------------------------------------------------------
# Evoco customers
# -----------------------------------------------------------------------
trakya_panel = get_or_create_partner("Trakya Panel Yapı A.Ş.", {
    'country_id': TR.id, 'currency_id': TRY.id,
    'vat': '1000000083', 'email': 'info@trakyapanel.com.tr', 'customer_rank': 1, 'city': 'Tekirdağ',
})
kuzey_sogutma = get_or_create_partner("Kuzey Soğutma Sistemleri A.Ş.", {
    'country_id': TR.id, 'currency_id': TRY.id,
    'vat': '1000000092', 'email': 'info@kuzeysogutma.com.tr', 'customer_rank': 1, 'city': 'Bursa',
})
konfor_yatak = get_or_create_partner("Konfor Yatak San. Ltd.", {
    'country_id': TR.id, 'currency_id': TRY.id,
    'vat': '1000000105', 'email': 'info@konforyatak.com.tr', 'customer_rank': 1, 'city': 'İnegöl',
})

env.cr.commit()

# -----------------------------------------------------------------------
# Supplier price lists (product.supplierinfo): 2-3 vendors per raw
# material, at different prices; dedicated vendor per service product.
# -----------------------------------------------------------------------
Product = env['product.template'].sudo()
SupplierInfo = env['product.supplierinfo'].sudo()
USD_TO_TRY = 34.50
EUR_TO_TRY = 37.20

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
assert areks, "Areks company not found - run 02_companies.py first"

hammadde_categs = env['product.category'].sudo().search(
    [('name', 'in', ['Polioller', 'İzosiyanatlar', 'Yardımcı Kimyasallar'])])
raw_materials = Product.search([('categ_id', 'in', hammadde_categs.ids)])

CHEM_SUPPLIERS = [nordpol, gulfstream, eastbridge, anatolia]


def supplier_price_in_its_currency(cost_try, supplier, variance):
    # NOTE: res.partner.currency_id is a non-stored COMPUTE field that
    # just mirrors the current env.company's currency - it is NOT
    # settable per-partner (confirmed: writing to it is silently
    # dropped). The real per-vendor billing currency lives in
    # property_purchase_currency_id, which we set explicitly on each
    # supplier partner above - use that instead.
    cur = supplier.property_purchase_currency_id
    if cur == USD:
        return round((cost_try / USD_TO_TRY) * variance, 4)
    if cur == EUR:
        return round((cost_try / EUR_TO_TRY) * variance, 4)
    return round(cost_try * variance, 2)


def get_or_create_supplierinfo(product_tmpl, supplier, price, delay):
    existing = SupplierInfo.search([
        ('product_tmpl_id', '=', product_tmpl.id),
        ('partner_id', '=', supplier.id),
    ], limit=1)
    if existing:
        # self-healing: two now-fixed bugs could have left an earlier
        # run's row wrong:
        # 1) unscoped standard_price read defaulting to an archived
        #    company -> price at/near 0.
        # 2) company_id defaults to self.env.company when omitted from
        #    create() vals (product.supplierinfo's own field default) -
        #    an odoo-bin shell session's env.company is NOT guaranteed
        #    to be a real/current company (it silently defaulted to an
        #    ARCHIVED one here), so every row created without an
        #    explicit company_id=False ended up scoped to that archived
        #    company instead of being a global (both-companies) vendor
        #    price - which then made Dropship's real _select_seller()
        #    resolution (unlike 10a_purchases.py's own direct, unscoped
        #    'mapped' lookup, which never exercises that filtering) find
        #    NO valid seller for the new companies at all.
        fix_vals = {}
        if abs(existing.price - price) > 0.001:
            fix_vals['price'] = price
        if existing.min_qty != 0.0:
            fix_vals['min_qty'] = 0.0
        if existing.company_id:
            fix_vals['company_id'] = False
        if fix_vals:
            existing.write(fix_vals)
            return existing, 'fixed'
        return existing, False
    SupplierInfo.create({
        'product_tmpl_id': product_tmpl.id,
        'partner_id': supplier.id,
        'price': price,
        'currency_id': supplier.property_purchase_currency_id.id,
        'delay': delay,
        'min_qty': 0.0,  # audit point 6: no artificial minimum order qty
        'company_id': False,  # global vendor price, visible to both companies
    })
    return None, True


created = 0
skipped = 0
fixed = 0
def shuffle_key(prod_name, supplier_name):
    # NOTE: a per-(product,supplier) hash is required here - adding a
    # single per-product scalar to each supplier's small, consecutive
    # partner id (then %100) barely reorders anything (no wraparound
    # for most hash values), which silently starved one vendor
    # (Anatolia) of any products on the first attempt. Hashing the
    # pair directly avoids that bias.
    return int(hashlib.md5(f"{prod_name}-{supplier_name}".encode('utf-8')).hexdigest(), 16) % 1000


for prod in raw_materials:
    is_isocyanate = prod.categ_id.name == 'İzosiyanatlar'
    h = int(hashlib.md5(prod.name.encode('utf-8')).hexdigest(), 16)
    count = 3 if is_isocyanate else (2 + (h % 2))  # isocyanates always get 3
    if is_isocyanate:
        # Eastbridge (specialist) always first
        others = [s for s in CHEM_SUPPLIERS if s != eastbridge]
        order = [eastbridge] + sorted(others, key=lambda s: shuffle_key(prod.name, s.name))
    else:
        order = sorted(CHEM_SUPPLIERS, key=lambda s: shuffle_key(prod.name, s.name))
    chosen = order[:count]
    for i, supplier in enumerate(chosen):
        h2 = int(hashlib.md5(f"{prod.name}-{supplier.name}".encode('utf-8')).hexdigest(), 16)
        variance = 0.92 + ((h2 % 2001) / 1000.0) * 0.20  # range [0.92, 1.12]
        # NOTE (bug found & fixed, same root cause as audit point 2): a bare
        # prod.standard_price resolves against env.company, which for an
        # odoo-bin shell session is not guaranteed to be Areks (it silently
        # fell back to an archived company here, reading 0.0) - scope
        # explicitly, since these raw materials are costed from Areks.
        price = supplier_price_in_its_currency(prod.with_company(areks).standard_price, supplier, variance)
        delay = 7 + (h2 % 24)  # 7-30 days
        _, was_created = get_or_create_supplierinfo(prod, supplier, price, delay)
        if was_created == 'fixed':
            fixed += 1
        elif was_created:
            created += 1
        else:
            skipped += 1

# service products -> dedicated vendor
SERVICE_SUPPLIER_MAP = [
    ("Gümrük Vergisi", marmara_gumruk),
    ("Gümrük Müşavirlik Hizmeti", marmara_gumruk),
    ("Navlun", bogazici_lojistik),
]
for name, supplier in SERVICE_SUPPLIER_MAP:
    prod = Product.search([('name', '=', name)], limit=1)
    assert prod, f"service product not found: {name}"
    price = round((prod.with_company(areks).standard_price or 1000.0), 2) or 1000.0
    _, was_created = get_or_create_supplierinfo(prod, supplier, price or 1000.0, 3)
    if was_created == 'fixed':
        fixed += 1
    elif was_created:
        created += 1
    else:
        skipped += 1

env.cr.commit()

print("-" * 70)
print(f"SUMMARY: contacts ready. supplierinfo created={created} fixed={fixed} skipped(existing)={skipped}")
print(f"  total product.supplierinfo rows: {SupplierInfo.search_count([])}")
print("=" * 70)
print("08_contacts.py done")
print("=" * 70)
