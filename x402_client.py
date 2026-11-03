#!/usr/bin/env python3
"""Akari x402 client — resolve the live host, then call free or paid routes.

Why this exists: the API host can change without notice (quick tunnel bound to the
process lifetime), so nothing should hardcode it. This file is the contract:

    from x402_client import resolve, free_get
    base = resolve()                     # cached, health-checked origin
    rows = free_get("/x402/dataset/preview")

CLI:
    python3 x402_client.py resolve
    python3 x402_client.py free /x402/dataset/preview
    python3 x402_client.py paid /x402/wallet-verdict?address=0x...   # needs x402_pay.py

No keys are read, stored or printed here.
"""
import json
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "https://edvyno.github.io/akari-proof/endpoint.json"
UA = "akari-x402-client/1.0"
_CACHE = {"origin": None, "ts": 0}


def _get(url, timeout=20, raw=False):
    """GET a URL. Parses JSON unless raw=True — free routes like /llms.txt are plain text,
    and a client that assumes JSON dies on the first non-JSON route it is handed."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/plain"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
        if raw:
            return r.status, body
        try:
            return r.status, json.loads(body)
        except Exception:
            return r.status, body


def resolve(max_age_s=600):
    """Return the live origin, verified against /health. Cached for max_age_s."""
    now = time.time()
    if _CACHE["origin"] and now - _CACHE["ts"] < max_age_s:
        return _CACHE["origin"]
    st, doc = _get(ENDPOINT)
    origin = (doc.get("url") or "").rstrip("/")
    if not origin:
        raise RuntimeError("endpoint.json has no url")
    age = now - float(doc.get("verified_ts") or 0)
    if age > 7200 or doc.get("health") != "ok":
        raise RuntimeError("endpoint.json is stale (%.0f min old, health=%s)" % (age / 60, doc.get("health")))
    try:
        hst, hdoc = _get(origin + "/health", timeout=10)
        if not (hst == 200 and hdoc.get("ok") is True):
            raise RuntimeError("origin answered but health is not ok")
    except Exception as e:
        raise RuntimeError("origin %s is not healthy: %s" % (origin, e))
    _CACHE.update(origin=origin, ts=now)
    return origin


def free_get(path, **params):
    """GET a free route. Returns the parsed JSON body."""
    base = resolve()
    url = base + path
    if params:
        q = "&".join("%s=%s" % (k, urllib.parse.quote(str(v))) for k, v in params.items())
        url += ("&" if "?" in url else "?") + q
    st, doc = _get(url)
    return doc


def paid_get(path, keychain_service="akari_deployer_key"):
    """GET a paid route by shelling out to the repo's x402_pay.py (never inlines keys)."""
    import subprocess
    base = resolve()
    out = subprocess.run([sys.executable, "scripts/x402_pay.py", base + path, keychain_service],
                         capture_output=True, text=True, timeout=180)
    return out.returncode, out.stdout


if __name__ == "__main__":
    import urllib.parse  # noqa: F401  (used by free_get)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "resolve"
    if cmd == "resolve":
        base = resolve()
        st, h = _get(base + "/health")
        print(json.dumps({"origin": base, "health": h.get("ok"), "protocol": h.get("protocol")}, indent=1))
    elif cmd == "free":
        path = sys.argv[2] if len(sys.argv) > 2 else "/x402/dataset/preview"
        doc = free_get(path)
        print(json.dumps(doc, indent=1)[:1200])
    elif cmd == "paid":
        rc, body = paid_get(sys.argv[2])
        print(rc, body[:800])
    else:
        print(__doc__)
