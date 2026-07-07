# Mini LinkedIn test fixture
Static fake-LinkedIn pages whose DOM satisfies the extension's `linkedin-messaging` and `linkedin-profile` content-script parsers, for Playwright e2e tests without linkedin.com.
Run: `python3 dev/mini-linkedin/serve.py` (port 8899 by default; pass a port as the first argument).
Open: http://localhost:8899/ (home, non-parseable), http://localhost:8899/messaging/thread/abc/ (messaging thread), http://localhost:8899/in/maya-lindqvist (profile).
