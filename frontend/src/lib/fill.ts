import { useLayoutEffect, useRef } from 'react';

/**
 * Sizes a scrolling list to the space actually left on screen below it (minus `reserve` px for anything that must
 * stay visible underneath, like action buttons), and keeps it right as the window changes. It only sets a CSS
 * variable, --fill, so the stylesheet decides where it applies (wide screens) and phones are untouched.
 */
export function useFillHeight<T extends HTMLElement>(reserve = 0, min = 240, ready = true) {  // `ready`: re-measure once the list exists
  const ref = useRef<T>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const screen = el.closest('.screen') as HTMLElement | null;
    const update = () => {
      const top = el.getBoundingClientRect().top + (screen?.scrollTop ?? 0);  // as if the page were scrolled to the top
      const bottom = screen ? screen.getBoundingClientRect().bottom - 40 : window.innerHeight - 40;  // the screen's bottom padding
      el.style.setProperty('--fill', `${Math.max(min, Math.floor(bottom - (top - (screen?.scrollTop ?? 0)) - reserve))}px`);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(document.documentElement);
    if (screen) ro.observe(screen);
    const t = window.setTimeout(update, 350);  // after the screen's entry animation settles
    return () => { ro.disconnect(); window.clearTimeout(t); };
  }, [reserve, min, ready]);
  return ref;
}
