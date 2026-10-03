"""
Banks for the recipient picker, with NIP codes (Liberty) and CBN codes (Paystack).
Paystack (CBN) codes come from GET https://api.paystack.co/bank and are what live payouts use. NIP codes are the commonly
published ones and only identify a bank for us today; check them against Liberty's list before bank-transfer funding goes live.
"""
BANKS = [
    ('Access Bank', '000014', '044'),
    ('Carbon', '100026', '565'),
    ('Citibank', '000009', '023'),
    ('Ecobank', '000010', '050'),
    ('FairMoney', '090551', '51318'),
    ('FCMB', '000003', '214'),
    ('Fidelity Bank', '000007', '070'),
    ('First Bank', '000016', '011'),
    ('Globus Bank', '000027', '00103'),
    ('GTBank', '000013', '058'),
    ('Jaiz Bank', '000006', '301'),
    ('Keystone Bank', '000002', '082'),
    ('Kuda', '090267', '50211'),
    ('Lotus Bank', '000029', '303'),
    ('Moniepoint', '090405', '50515'),
    ('MTN MoMo PSB', '120003', '120003'),
    ('OPay', '100004', '999992'),
    ('Paga', '100002', '100002'),
    ('PalmPay', '100033', '999991'),
    ('Polaris Bank', '000008', '076'),
    ('Providus Bank', '000023', '101'),
    ('Smartcash PSB (Airtel)', '120004', '120004'),
    ('Sparkle', '090325', '51310'),
    ('Stanbic IBTC', '000012', '221'),
    ('Standard Chartered', '000021', '068'),
    ('Sterling Bank', '000001', '232'),
    ('TAJ Bank', '000026', '302'),
    ('Titan Trust Bank', '000025', '102'),
    ('UBA', '000004', '033'),
    ('Union Bank', '000018', '032'),
    ('Unity Bank', '000011', '215'),
    ('VFD Microfinance Bank', '090110', '566'),
    ('Wema Bank', '000017', '035'),
    ('Zenith Bank', '000015', '057'),
]
BY_NIP = {nip: (name, cbn) for name, nip, cbn in BANKS}
