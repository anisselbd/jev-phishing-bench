"""Control 1: a baseline with no AI at all.

Two binary features computed from the email alone:
- ``hosting_or_shortener``: the link's host belongs to a generic list of URL shorteners, QR-code shorteners, free
  hosting and static-site platforms, IPFS gateways and document-sharing hosts. The list is written from public
  knowledge of such services; the dataset's own ``url_category`` labels are never used.
- ``etld1_mismatch``: the registered domain (eTLD+1, public suffix list) of the sender address differs from the
  registered domain of the link.

If Jev's signal questions do not beat these two lines of code, the dataset separates by construction.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import tldextract

# Bundled public-suffix snapshot only, no network fetch, so results are reproducible offline.
_extract = tldextract.TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)

# Registered domains (eTLD+1) of shorteners, free hosting, static-site platforms, IPFS gateways and file sharing.
FREE_HOSTING_DOMAINS = {
    # URL shorteners and QR-code shorteners
    "bit.ly", "tinyurl.com", "t.co", "is.gd", "goo.gl", "ow.ly", "buff.ly", "cutt.ly", "rebrand.ly", "shorturl.at",
    "tiny.cc", "rb.gy", "short.gy", "t.ly", "lnkd.in", "qrco.de", "q-r.to", "qr.io", "me-qr.com", "s.id", "surl.li",
    # static hosting and app platforms
    "github.io", "gitlab.io", "web.app", "firebaseapp.com", "vercel.app", "netlify.app", "pages.dev", "workers.dev",
    "herokuapp.com", "glitch.me", "repl.co", "replit.app", "surge.sh", "render.com", "onrender.com", "fly.dev",
    "r2.dev", "azurewebsites.net", "azurestaticapps.net", "appspot.com", "cloudfront.net", "amazonaws.com",
    "s3.amazonaws.com", "storage.googleapis.com", "googleusercontent.com",
    # website builders and blogs
    "weebly.com", "wixsite.com", "wix.com", "webnode.com", "webnode.page", "jimdosite.com", "jimdofree.com",
    "blogspot.com", "wordpress.com", "godaddysites.com", "square.site", "strikingly.com", "carrd.co", "yolasite.com",
    "webflow.io", "framer.app", "framer.website", "boxmode.io", "webstudio.is", "teemill.com", "webcindario.com",
    "000webhostapp.com", "byethost.com", "wcomhost.com", "ghost.io", "notion.site", "super.site", "tilda.ws",
    # IPFS gateways
    "ipfs.io", "dweb.link", "cloudflare-ipfs.com", "cf-ipfs.com", "w3s.link", "infura-ipfs.io", "nftstorage.link",
    "ipfs.fleek.co", "4everland.io", "pinata.cloud", "gateway.pinata.cloud", "ipfs.eth.aragon.network",
    # forms, docs and file sharing on big platforms (full hosts, matched exactly)
}
FREE_HOSTING_HOSTS = {
    "docs.google.com", "drive.google.com", "sites.google.com", "forms.gle", "forms.office.com", "1drv.ms",
    "onedrive.live.com", "sharepoint.com", "dropbox.com", "www.dropbox.com", "box.com", "app.box.com",
    "wetransfer.com", "we.tl", "mega.nz", "mediafire.com", "sendgrid.net", "storage.cloud.google.com",
    "firebasestorage.googleapis.com", "acrobat.adobe.com", "documentcloud.adobe.com", "canva.site", "www.canva.com",
}

_EMAIL_RE = re.compile(r"[\w.+-]+@([\w.-]+)")


def registered_domain(host: str) -> str:
    ext = _extract(host.lower())
    return ext.top_domain_under_public_suffix if ext.top_domain_under_public_suffix else host.lower()


def link_host(url: str) -> str:
    return urlparse(url.strip()).netloc.lower().split(":")[0]


def sender_domain(from_field: str) -> str:
    m = _EMAIL_RE.search(from_field or "")
    return m.group(1).lower() if m else ""


def features(email: dict) -> dict[str, float]:
    host = link_host(email["link_url"])
    reg = registered_domain(host)
    hosting = 1.0 if (reg in FREE_HOSTING_DOMAINS or host in FREE_HOSTING_HOSTS) else 0.0
    sender = sender_domain(email["from"])
    mismatch = 1.0 if (sender and registered_domain(sender) != reg) else 0.0
    return {"hosting_or_shortener": hosting, "etld1_mismatch": mismatch}


HEURISTIC_FEATURES = ["hosting_or_shortener", "etld1_mismatch"]
