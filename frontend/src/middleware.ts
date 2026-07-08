// Route-guard middleware (redirect UX only).
//
// The real access token lives in memory and the refresh token is an httpOnly
// cookie on the API origin — neither is visible here. So this middleware gates
// on a same-origin, non-secret "session hint" cookie (pt_session) that the
// client sets on login and clears on logout. Security is always enforced
// server-side by the API's Bearer-token checks; this only avoids flashing a
// protected page (or the auth pages) to the wrong audience.

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const AUTH_PAGES = ["/login", "/register"];
const SESSION_HINT_COOKIE = "pt_session";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.get(SESSION_HINT_COOKIE)?.value === "1";
  const isAuthPage = AUTH_PAGES.some((p) => pathname === p || pathname.startsWith(p + "/"));

  // Signed-in users have no reason to see login/register.
  if (hasSession && isAuthPage) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  // Unauthenticated users are sent to sign-in from any protected route.
  if (!hasSession && !isAuthPage) {
    const url = new URL("/login", request.url);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

// Run on everything except Next internals, static assets, and API proxying.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
