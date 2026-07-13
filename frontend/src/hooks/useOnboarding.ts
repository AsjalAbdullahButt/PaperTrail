"use client";

import { useEffect, useState } from "react";

const KEY = "papertrail_onboarded";

/** First-login onboarding hint, dismissed permanently in localStorage. */
export function useOnboarding(authed: boolean | null) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (authed === true && !window.localStorage.getItem(KEY)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing from localStorage, not derivable during render
      setShow(true);
    }
  }, [authed]);

  function dismiss() {
    window.localStorage.setItem(KEY, "1");
    setShow(false);
  }

  return { showOnboarding: show, dismissOnboarding: dismiss };
}
