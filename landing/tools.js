/* Calculators on spendrip.com guides. Plain JS, no tracking. Fee rules match the app (engine/fees.py). */
(function () {
  var N = function (k) { return '₦' + Math.round(k / 100).toLocaleString('en-NG'); };
  var num = function (el) { return Math.max(0, Number(String(el.value).replace(/[^\d.]/g, '')) || 0); };
  function fees(amountKobo) {
    var provider = amountKobo <= 500000 ? 1000 : amountKobo <= 5000000 ? 2500 : 5000;
    var duty = amountKobo >= 1000000 ? 5000 : 0;
    return { service: 5000, provider: provider, duty: duty, total: 5000 + provider + duty };
  }
  function on(el, fn) { el.addEventListener('input', fn); fn(); }

  // Fee calculator: one drip of ₦X, N times a month.
  document.querySelectorAll('[data-calc="fees"]').forEach(function (box) {
    var amt = box.querySelector('[name=amount]'), times = box.querySelector('[name=times]'), out = box.querySelector('.out');
    function run() {
      var a = num(amt) * 100, n = Math.max(1, Math.round(num(times)) || 1), f = fees(a);
      out.innerHTML =
        '<div><span>SpenDrip fee</span><span>' + N(f.service) + '</span></div>' +
        '<div><span>Transfer fee (Paystack)</span><span>' + N(f.provider) + '</span></div>' +
        '<div><span>Stamp duty' + (f.duty ? '' : ' (under ₦10,000: none)') + '</span><span>' + N(f.duty) + '</span></div>' +
        '<div class="total"><span>Each drip costs</span><span>' + N(a + f.total) + '</span></div>' +
        '<div><span>' + n + ' drip' + (n > 1 ? 's' : '') + ' a month</span><span>' + N(n * (a + f.total)) + ' (' + N(n * f.total) + ' in fees)</span></div>';
    }
    on(amt, run); times.addEventListener('input', run);
  });

  // Black tax calculator: share of take-home pay sent to family.
  document.querySelectorAll('[data-calc="blacktax"]').forEach(function (box) {
    var pay = box.querySelector('[name=pay]'), fam = box.querySelector('[name=family]'), out = box.querySelector('.out');
    function run() {
      var p = num(pay) * 100, s = num(fam) * 100, f = fees(s), share = p ? (s / p) * 100 : 0;
      out.innerHTML =
        '<div class="total"><span>Share of your take-home pay</span><span>' + share.toFixed(1) + '%</span></div>' +
        '<div><span>Every year</span><span>' + N(s * 12) + '</span></div>' +
        '<div><span>Left each month after family support</span><span>' + N(Math.max(0, p - s)) + '</span></div>' +
        '<div><span>Sending it as one monthly drip costs</span><span>' + N(f.total) + ' in fees a month</span></div>';
    }
    on(pay, run); fam.addEventListener('input', run);
  });
})();
