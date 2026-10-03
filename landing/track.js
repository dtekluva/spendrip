/* spendrip.com: remember where a visitor first came from, carry it into the app on sign-up links, and count
   "Get started" / "Sign in" clicks in Umami (stats.spendrip.com, cookieless). The source lives only in this
   browser's localStorage. */
(function () {
  var KEY = 'sd-src';
  var SOURCES = [
    [/(^|\.)google\./, 'google'], [/(^|\.)bing\./, 'bing'], [/duckduckgo/, 'duckduckgo'], [/yahoo/, 'yahoo'],
    [/chatgpt\.com|openai\.com/, 'chatgpt'], [/perplexity/, 'perplexity'], [/gemini\.google/, 'gemini'], [/claude\.ai/, 'claude'],
    [/copilot\.microsoft/, 'copilot'], [/whatsapp|wa\.me/, 'whatsapp'], [/(^|\.)t\.co$|twitter|(^|\.)x\.com$/, 'x'],
    [/facebook|fb\.com|messenger/, 'facebook'], [/instagram/, 'instagram'], [/linkedin|lnkd\.in/, 'linkedin'],
    [/tiktok/, 'tiktok'], [/nairaland/, 'nairaland'], [/reddit/, 'reddit'], [/youtube|youtu\.be/, 'youtube']
  ];
  function host(u) { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } }
  function detect() {
    var q = new URLSearchParams(location.search), utm = q.get('utm_source');
    if (utm) return ('utm:' + utm + (q.get('utm_campaign') ? '/' + q.get('utm_campaign') : '')).slice(0, 80);
    var h = host(document.referrer);
    if (!h || /(^|\.)spendrip\.com$/.test(h)) return '';
    for (var i = 0; i < SOURCES.length; i++) if (SOURCES[i][0].test(h)) return SOURCES[i][1];
    return h.slice(0, 80);
  }
  var src = null;
  try { src = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { /* storage blocked */ }
  if (!src) {
    src = { s: detect() || 'direct', p: location.pathname.slice(0, 120) };
    try { localStorage.setItem(KEY, JSON.stringify(src)); } catch (e) { /* fine */ }
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href^="https://app.spendrip.com"]');
    if (!a) return;
    var u = new URL(a.href);
    u.searchParams.set('src', src.s);
    u.searchParams.set('lp', src.p);
    a.href = u.toString();
    var name = /sign in/i.test(a.textContent) ? 'sign-in' : 'get-started';
    if (window.umami) window.umami.track(name, { page: location.pathname, source: src.s });
  }, true);
})();
