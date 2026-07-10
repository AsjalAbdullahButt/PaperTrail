import { useEffect, useState, type RefObject } from "react";

/** Tracks an anchor element's viewport rect while `active`, so a floating
 * panel (dropdown, tooltip, menu) can be portaled to <body> and positioned
 * with `position: fixed` instead of nesting a `position: absolute` child
 * inside the anchor's own DOM subtree.
 *
 * The nested-absolute approach breaks under a common trap: any ancestor with
 * `backdropFilter` (or `filter`, `transform`, `opacity < 1`, …) opens a new
 * CSS stacking context per spec, and a z-index inside that context only ranks
 * the element within it — it can still end up rendered below a later, higher
 * DOM sibling of the ancestor itself. Portaling to <body> sidesteps that
 * entirely. */
export function useFloatingRect(anchorRef: RefObject<HTMLElement | null>, active: boolean) {
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (!active || !anchorRef.current) {
      setRect(null);
      return;
    }
    const update = () => setRect(anchorRef.current?.getBoundingClientRect() ?? null);
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [active, anchorRef]);

  return rect;
}
