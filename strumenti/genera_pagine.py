#!/usr/bin/env python3
"""
Caborca · crea una pagina vera per ogni articolo, per Google.

Gira da solo su GitHub (vedi .github/workflows/pubblica.yml) ogni volta che
il sito cambia, per esempio quando pubblichi un articolo dal pannello.
Non modifica nulla nel repository: lavora solo sulla copia che va online.

Crea:
  testi/<titolo>/index.html   una pagina per ogni articolo pubblicato
  sitemap.xml                 l'elenco delle pagine, da dare a Google
  robots.txt                  dice a Google dove trovare la sitemap
e aggiunge a index.html la descrizione del sito.
"""
import html
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

SITO = "https://caborca.it"
NOME = "Caborca"
DESCRIZIONE_SITO = ("Caborca è una rivista online di letteratura: saggi, racconti, "
                    "poesie, recensioni di libri e traduzioni.")
RUBRICHE = {"saggio": "Saggi", "contemporaneo": "Contemporaneo", "racconto": "Racconti",
            "poesia": "Poesia", "libri": "Libri"}

CARTELLA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slug(s):
    """Lo stesso indirizzo che usa il sito (funzione slug in index.html)."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if not ("̀" <= c <= "ͯ"))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60]


def esc(s):
    return html.escape(s or "", quote=True)


def inline(s):
    s = esc(s)
    s = re.sub(r"\{([^{}|]+)\|([^{}]+)\}", r"\1", s)                       # glossario: resta la parola
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", s)
    s = re.sub(r"_([^_]+)_", r"<i>\1</i>", s)
    return s


def corpo_html(md):
    out = []
    for b in re.split(r"\n\s*\n", (md or "").replace("\r", "")):
        b = b.strip()
        if not b:
            continue
        m = re.match(r"^\[\[(foto|galleria) (.*)\]\]$", b, re.S)
        if m:
            try:
                d = json.loads(m.group(2))
                foto = [d] if m.group(1) == "foto" else d.get("foto", [])
                for f in foto:
                    out.append('<figure><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>'
                               % (esc(f.get("src")), esc(f.get("didascalia")), esc(f.get("didascalia"))))
            except Exception:
                pass
            continue
        m = re.match(r"^\[\[nota (.*)\]\]$", b, re.S)
        if m:
            out.append("<aside><p>%s</p></aside>" % inline(m.group(1)))
            continue
        m = re.match(r"^#{2,3}\s+(.*)$", b)
        if m:
            out.append("<h2>%s</h2>" % inline(m.group(1)))
            continue
        if b.startswith(">"):
            out.append("<blockquote><p>%s</p></blockquote>" % inline(re.sub(r"^>\s?", "", b, flags=re.M)))
            continue
        if re.match(r"^[-*]\s", b):
            righe = "".join("<li>%s</li>" % inline(re.sub(r"^[-*]\s+", "", r)) for r in b.split("\n"))
            out.append("<ul>%s</ul>" % righe)
            continue
        out.append("<p>%s</p>" % inline(b).replace("\n", "<br>"))
    return "\n".join(out)


def testo_semplice(md):
    t = re.sub(r"\[\[.*?\]\]", " ", md or "", flags=re.S)
    t = re.sub(r"\{([^{}|]+)\|[^{}]+\}", r"\1", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[#>*_]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def taglia(t, n=158):
    t = re.sub(r"\s+", " ", t or "").strip()
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def data_iso(v):
    v = (v or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        return "%s-%s-%s" % m.groups()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", v)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    return ""


def assoluto(src):
    if not src:
        return ""
    if src.startswith("http"):
        return src
    return SITO + (src if src.startswith("/") else "/" + src)


def testa(titolo, descrizione, url, tipo="website", immagine="", extra=""):
    righe = [
        '<meta name="caborca-pagine" content="1">',
        '<meta name="description" content="%s">' % esc(descrizione),
        '<link rel="canonical" href="%s">' % esc(url),
        '<meta property="og:site_name" content="%s">' % NOME,
        '<meta property="og:locale" content="it_IT">',
        '<meta property="og:type" content="%s">' % tipo,
        '<meta property="og:title" content="%s">' % esc(titolo),
        '<meta property="og:description" content="%s">' % esc(descrizione),
        '<meta property="og:url" content="%s">' % esc(url),
        '<meta name="twitter:card" content="%s">' % ("summary_large_image" if immagine else "summary"),
    ]
    if immagine:
        righe.append('<meta property="og:image" content="%s">' % esc(immagine))
    return "\n".join(righe) + extra + "\n"


def main():
    with open(os.path.join(CARTELLA, "index.html"), encoding="utf-8") as f:
        base = f.read()
    try:
        with open(os.path.join(CARTELLA, "contenuti", "testi.json"), encoding="utf-8") as f:
            dati = json.load(f)
    except Exception as e:
        print("Non riesco a leggere contenuti/testi.json:", e)
        dati = {"testi": []}

    testi = [t for t in dati.get("testi", []) if t.get("pubblicato") is not False and t.get("titolo")]
    oggi = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if "</head>" not in base or "<title>" not in base:
        print("index.html non ha <head> o <title>: mi fermo senza toccare niente.")
        return 0

    # home
    home = base.replace("</head>", testa(NOME + " — rivista di letteratura", DESCRIZIONE_SITO, SITO + "/") + "</head>", 1)
    with open(os.path.join(CARTELLA, "index.html"), "w", encoding="utf-8") as f:
        f.write(home)

    pagine = [(SITO + "/", oggi)]
    visti = set()
    for t in testi:
        id_ = slug(t["titolo"])
        if not id_ or id_ in visti:
            continue
        visti.add(id_)
        url = "%s/testi/%s/" % (SITO, id_)
        autore = (t.get("autore") or "").strip()
        rubrica = RUBRICHE.get(t.get("rubrica"), "")
        titolo_pagina = t["titolo"] + (" — " + autore if autore else "") + " · " + NOME
        descr = taglia(t.get("sottotitolo") or testo_semplice(t.get("corpo")))
        quando = data_iso(t.get("data"))
        img = assoluto(t.get("copertina"))
        ld = {
            "@context": "https://schema.org", "@type": "Article",
            "headline": t["titolo"][:110], "description": descr, "inLanguage": "it",
            "mainEntityOfPage": url, "url": url,
            "publisher": {"@type": "Organization", "name": NOME, "url": SITO + "/"},
        }
        if autore:
            ld["author"] = {"@type": "Person", "name": autore}
        if quando:
            ld["datePublished"] = quando
        if img:
            ld["image"] = img
        if rubrica:
            ld["articleSection"] = rubrica
        extra = ('\n<script>window.CABORCA_TESTO=%s</script>' % json.dumps(id_) +
                 '\n<script type="application/ld+json">%s</script>' % json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))

        pagina = base.replace("<title>Caborca — rivista di letteratura</title>", "<title>%s</title>" % esc(titolo_pagina), 1)
        pagina = pagina.replace("</head>", testa(titolo_pagina, descr, url, "article", img, extra) + "</head>", 1)
        # il testo dell'articolo, leggibile anche da chi non esegue il JavaScript
        senza_js = ('<noscript><article class="testo-statico"><p>%s</p><h1>%s</h1>%s%s%s</article></noscript>'
                    % (esc(rubrica), esc(t["titolo"]),
                       "<p><i>%s</i></p>" % esc(t.get("sottotitolo")) if t.get("sottotitolo") else "",
                       "<p>di %s</p>" % esc(autore) if autore else "",
                       corpo_html(t.get("corpo"))))
        pagina = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + senza_js, pagina, count=1)

        cartella = os.path.join(CARTELLA, "testi", id_)
        os.makedirs(cartella, exist_ok=True)
        with open(os.path.join(cartella, "index.html"), "w", encoding="utf-8") as f:
            f.write(pagina)
        pagine.append((url, min(quando, oggi) if quando else oggi))

    voci = "".join("  <url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (esc(u), d) for u, d in pagine)
    with open(os.path.join(CARTELLA, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s</urlset>\n' % voci)
    with open(os.path.join(CARTELLA, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nDisallow: /admin/\nDisallow: /strumenti/\n\nSitemap: %s/sitemap.xml\n" % SITO)

    print("Pagine create: %d articoli + la home." % (len(pagine) - 1))
    for u, _ in pagine:
        print("  " + u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
