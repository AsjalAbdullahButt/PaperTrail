"use client";

import { useEffect, useState } from "react";
import { Toaster } from "react-hot-toast";

/** Global chrome: toast host + an offline banner. Mounted once in the layout. */
export default function AppChrome() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  return (
    <>
      {offline && (
        <div
          role="status"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 100,
            padding: "8px 16px",
            textAlign: "center",
            fontSize: 13.5,
            fontWeight: 600,
            color: "#3a2c05",
            background: "#e0a53a",
          }}
        >
          You&rsquo;re offline — queries and uploads are paused.
        </div>
      )}
      <Toaster position="bottom-right" toastOptions={{ duration: 4000 }} />
    </>
  );
}
