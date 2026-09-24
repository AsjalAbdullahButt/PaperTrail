# Authentication and Session Management

## JWT-based, stateless authentication

PaperTrail authenticates users with JSON Web Tokens rather than server-side session storage, which is what allows any stateless API worker to serve any authenticated request without sticky sessions or a shared session store. Access tokens are short-lived: the default expiry, configured by `JWT_EXPIRE_MINUTES`, is 30 minutes. Tokens are signed using the algorithm named in `JWT_ALGORITHM`, which defaults to `HS256`, with the signing key coming from the `JWT_SECRET` setting.

## Refresh tokens and rotation

Because a 30-minute access token would otherwise force a user to re-enter their password every half hour, PaperTrail issues a longer-lived refresh token alongside the access token. The refresh token defaults to a 7-day lifetime, configured by `REFRESH_EXPIRE_DAYS`, and is stored in an httpOnly cookie — meaning client-side JavaScript cannot read it, which limits its exposure to cross-site-scripting attacks — under a cookie name configured by `REFRESH_COOKIE_NAME` (default `papertrail_refresh`). When an access token expires, the frontend uses the refresh token to obtain a new access token without asking the user to log in again. The refresh mechanism includes theft detection: if a refresh token that has already been rotated (used and replaced) is presented again, this is treated as a signal that the token may have been stolen and reused.

## The insecure default secret and the production safety check

The `JWT_SECRET` setting has a deliberately obvious, insecure default value used only for local development, so that developers immediately recognize an unconfigured secret rather than mistaking it for a real one. PaperTrail refuses to even start in a configuration that looks like production (specifically, when `COOKIE_SECURE=true`, which marks the refresh cookie as HTTPS-only) while still using that default development `JWT_SECRET`. If both conditions are true, the application raises a `RuntimeError` during startup with a message instructing the operator to set a unique secret, generated for example with `openssl rand -hex 32`. This check exists because a production deployment signing tokens with a publicly known default key would let any visitor forge a valid access token for any account.

## Password handling and the cookie security flag

Passwords are hashed using bcrypt via the `passlib` library rather than being stored or compared in plaintext. The `COOKIE_SECURE` setting controls whether the refresh cookie is marked `Secure` (sent only over HTTPS); it defaults to `false` for local development over plain HTTP, and must be set to `true` in any production deployment, which is exactly the setting that triggers the insecure-default-secret startup check described above.

## CORS and the frontend base URL

Two related but distinct settings govern how the backend interacts with the browser. `CORS_ORIGINS` is a comma-separated allow-list of browser origins permitted to make cross-origin requests to the API; it is parsed into a list with empty entries dropped. `FRONTEND_BASE_URL` is a separate setting used to build absolute links that get emailed or logged to users — most notably, the password-reset link — and is not itself a CORS setting. Both settings must point at the same final deployed frontend URL; if either one is left stale (for example, still pointing at `localhost` after deploying), the practical symptom differs depending on which one is wrong: a stale `CORS_ORIGINS` causes the browser to silently reject API responses due to a CORS policy violation, while a stale `FRONTEND_BASE_URL` causes password-reset emails to contain a link pointing at the wrong host entirely.
