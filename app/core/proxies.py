"""Proxies whose X-Forwarded-For entries are trusted when resolving the client address.

Observed on Render (2026-11-23): a request reaches the app through Cloudflare and then Render's
internal load balancer, and X-Forwarded-For arrives as

    <anything the client sent>, <client>, <Cloudflare edge>, <Render internal 10.x>

Render appends to a client-supplied header instead of replacing it, so the leftmost entry is
spoofable. Uvicorn walks the list from the right, skipping trusted proxies, and takes the first
untrusted address: with only private networks and Cloudflare trusted, that is the real client,
and whatever the client prepended is never reached.

If a hop ever comes from an address missing here, the client resolves to that proxy instead:
clients then share a rate-limit bucket (fails closed), they never get to choose their own.
"""

# RFC 1918 / loopback / IPv6 unique-local: Render's internal hops and local development.
_PRIVATE_NETWORKS = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "::1/128",
    "fc00::/7",
)

# Published at https://www.cloudflare.com/ips-v4 and /ips-v6 (fetched 2026-11-23).
_CLOUDFLARE_NETWORKS = (
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
)

TRUSTED_PROXY_NETWORKS: tuple[str, ...] = _PRIVATE_NETWORKS + _CLOUDFLARE_NETWORKS
