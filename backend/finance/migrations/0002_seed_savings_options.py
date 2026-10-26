from django.db import migrations

OPTIONS = [
    ("Treasury bills", "Government security", "Short-term loans to the Federal Government, sold through banks and investment platforms. "
     "You get your money back with interest at the end of 91, 182 or 364 days.", "Very low: backed by the Federal Government",
     "Locked until the end of the term", "Central Bank of Nigeria", "https://www.cbn.gov.ng/rates/"),
    ("FGN Savings Bond", "Government security", "Sold by the Debt Management Office every month for 2 or 3 years, from small amounts, "
     "with interest paid every quarter.", "Very low: backed by the Federal Government", "2 or 3 years; can be sold early on the exchange",
     "Debt Management Office", "https://www.dmo.gov.ng"),
    ("Money market funds", "Mutual fund", "Pooled funds run by SEC-registered fund managers that invest in treasury bills and bank "
     "deposits. Most let you withdraw within a few working days.", "Low, but returns aren't guaranteed", "Usually 1 to 3 working days",
     "Securities and Exchange Commission", "https://sec.gov.ng"),
    ("Savings or target-savings account", "Bank account", "An interest-paying account at a licensed bank or microfinance bank. "
     "Deposits at licensed banks are insured by the NDIC up to its limit.", "Low at licensed banks (NDIC insured)",
     "Usually any time; target accounts may lock your money", "NDIC", "https://ndic.gov.ng"),
    ("Emergency fund", "A habit, not a product", "Before investing, many people keep three to six months of essentials in an account "
     "they can reach quickly, so a surprise doesn't become a loan.", "", "Any time", "", ""),
]


def seed(apps, schema_editor):
    SavingsOption = apps.get_model("finance", "SavingsOption")
    for i, (name, kind, summary, risk, access, src, url) in enumerate(OPTIONS):
        SavingsOption.objects.get_or_create(name=name, defaults={"kind": kind, "summary": summary, "risk": risk, "access": access,
                                                                  "source_name": src, "source_url": url, "order": i})


class Migration(migrations.Migration):
    dependencies = [("finance", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
