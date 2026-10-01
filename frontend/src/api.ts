export interface Summary {
  balance: { available_kobo: number; held_kobo: number; total_kobo: number };
  forecast: {
    protected_kobo: number;
    free_kobo: number;
    total_needed_kobo: number;
    top_up_kobo: number;
    events: { plan_id: number; at: string; amount_kobo: number; status: string; rank: number | null }[];
  };
  funding_account: { account_number: string; bank_name: string } | null;
}

export const naira = (kobo: number) => '₦' + Math.round(kobo / 100).toLocaleString('en-NG');

export async function getSummary(): Promise<Summary> {
  const r = await fetch('/api/summary', { credentials: 'include' });
  if (!r.ok) throw new Error(`Couldn't load your balance (${r.status})`);
  return r.json();
}
