"""
Banks for the recipient picker, with NIP codes (Liberty) and CBN codes (Paystack).
Check this list against Liberty's before going live; codes here are the commonly published ones.
"""
BANKS = [
    ("Access Bank", "000014", "044"),
    ("Ecobank", "000010", "050"),
    ("Fidelity Bank", "000007", "070"),
    ("First Bank", "000016", "011"),
    ("FCMB", "000003", "214"),
    ("GTBank", "000013", "058"),
    ("Keystone Bank", "000002", "082"),
    ("Kuda", "090267", "50211"),
    ("Moniepoint", "090405", "50515"),
    ("OPay", "100004", "999992"),
    ("PalmPay", "100033", "999991"),
    ("Polaris Bank", "000008", "076"),
    ("Providus Bank", "000023", "101"),
    ("Stanbic IBTC", "000012", "221"),
    ("Sterling Bank", "000001", "232"),
    ("UBA", "000004", "033"),
    ("Union Bank", "000018", "032"),
    ("Wema Bank", "000017", "035"),
    ("Zenith Bank", "000015", "057"),
]
BY_NIP = {nip: (name, cbn) for name, nip, cbn in BANKS}
