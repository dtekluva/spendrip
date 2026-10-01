import { useEffect, useState } from 'react';
import { getSummary, naira, type Summary } from './api';

// Phase 0 placeholder: proves the React app talks to the Django API.
// The real screens (from docs/mock/spendrip-mock.html) arrive in Phase 2.
export default function App() {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState('');

  useEffect(() => { getSummary().then(setData).catch((e) => setError(e.message)); }, []);

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 480, margin: '40px auto', padding: '0 16px', color: '#0E1233' }}>
      <h1 style={{ marginBottom: 4 }}>spendrip</h1>
      <p style={{ marginTop: 0, color: '#5D6390' }}>Money that shows up on time.</p>
      {error && <p style={{ color: '#E5484D' }}>{error}. Is the backend running and seeded?</p>}
      {data && (
        <section style={{ display: 'grid', gap: 8 }}>
          <div>Balance: <b>{naira(data.balance.available_kobo)}</b></div>
          <div>Protected for priorities: <b>{naira(data.forecast.protected_kobo)}</b></div>
          <div>Free to spend: <b>{naira(Math.max(0, data.forecast.free_kobo))}</b></div>
          <div>Rest of this month needs: <b>{naira(data.forecast.total_needed_kobo)}</b></div>
          <div>Top up to cover everything: <b>{naira(data.forecast.top_up_kobo)}</b></div>
          <div>Drips left this month: <b>{data.forecast.events.length}</b> ({data.forecast.events.filter((e) => e.status === 'wait').length} waiting)</div>
          {data.funding_account && <div>Fund it: <b>{data.funding_account.account_number}</b> · {data.funding_account.bank_name}</div>}
        </section>
      )}
    </main>
  );
}
