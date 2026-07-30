# Security

Kemi-Claw is intended only for systems you own or have explicit written permission to test.

## Deployment checklist

1. Generate unique, high-entropy values for `KEMI_API_KEY` and `KEMI_JWT_SECRET`.
2. Keep Redis and Flower private; place HTTP services behind TLS and a trusted reverse proxy.
3. Set `KEMI_TELEGRAM_ALLOWED_IDS` before enabling Telegram.
4. Run workers in an isolated environment with minimal network and filesystem privileges.
5. Review plugins before loading them; plugin code executes in the worker process.
6. Rotate model and integration credentials regularly and never commit `.env`.
7. Back up and protect the `kemi-data` volume because it contains users and scan memory.

The `authorized` field records operator confirmation; it is not a substitute for a written scope agreement or network-level egress controls.
