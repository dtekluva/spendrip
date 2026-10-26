import { api } from '../lib/api';
import { N } from '../lib/format';
import type { Store } from '../lib/store';
import type { Plan } from '../lib/types';
import { Confirm } from '../components/Confirm';

/** "Are you sure?" before pausing or resuming: these change what money goes out, so they get a second step. */

export const confirmPauseAll = (store: Store) => (
  <Confirm mood="sleep" title="Pause all your drips?" yes="Yes, pause all" no="No, keep sending" danger
    body={<>Nothing will go out until you resume, <b>including your priorities</b>. The people you pay won't get their money on time. Nothing is deleted.</>}
    onYes={async () => {
      await api.patch('/me/settings', { paused_all: true });
      await Promise.all([store.reload(), store.refreshMe()]);
      store.closeSheet(); store.toast('All drips paused');
    }} />
);

export const confirmResumeAll = (store: Store) => (
  <Confirm mood="happy" title="Resume all your drips?" yes="Yes, resume" no="Not yet"
    body={<>Drips go out again from their next scheduled time. Anything that was due while paused isn't sent later.
      {store.summary?.forecast.top_up_kobo ? <> To cover the rest of this month, add {N(store.summary.forecast.top_up_kobo)}.</> : null}</>}
    onYes={async () => {
      await api.patch('/me/settings', { paused_all: false });
      await Promise.all([store.reload(), store.refreshMe()]);
      store.closeSheet(); store.toast('All drips are back on');
    }} />
);

/** One plan. `back` reopens whatever sheet the person came from (e.g. the plan's own sheet). */
export const confirmPlanPause = (store: Store, p: Plan, back?: () => void) => {
  const pausing = p.status === 'active';
  return (
    <Confirm mood={pausing ? 'sleep' : 'happy'} danger={pausing}
      title={pausing ? `Pause ${p.label}?` : `Resume ${p.label}?`}
      yes={pausing ? 'Yes, pause' : 'Yes, resume'} no={pausing ? 'No, keep sending' : 'Not yet'}
      body={pausing
        ? <>No drips for {p.label} go out until you resume it{p.priority_rank ? <>, and it stops being protected as <b>priority {p.priority_rank}</b> while paused</> : null}. Nothing is deleted.</>
        : <>{p.label} sends again from its next scheduled time. Anything that was due while paused isn't sent later.</>}
      onStop={back}
      onYes={async () => {
        await api.patch(`/plans/${p.id}`, { status: pausing ? 'paused' : 'active' });
        await store.reload();
        store.toast(pausing ? `${p.label} paused` : `${p.label} is sending again`);
        if (back) back(); else store.closeSheet();
      }} />
  );
};
