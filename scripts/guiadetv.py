"""
EXTRATOR PROPRIO DO GUIADETV.COM

O extrator do iptv-org parou de ler o guiadetv (o site mudou o layout em
2026). Este le a pagina nova direto: cada programa e um <li> com
  <time datetime="2026-10-05T21:15:00-03:00">  (inicio, com fuso)
  <span>3h</span>                              (duracao)
  <a href="/programa/...">Titulo</a>
  <p>descricao</p>
Uma pagina traz ~8 dias. Fim de cada programa = inicio do seguinte (o
ultimo usa a duracao).

Le os canais do guiadetv em trabalho/canais.channels.xml e grava
trabalho/guiadetv.com.xml (o mesmo formato que o iptv-org grava), que o
juntar_guia.py usa normalmente. Se o site mudar de novo, cai para o
"no ar agora / a seguir" que a pagina tambem traz (dados estruturados).
"""
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRABALHO = os.path.join(RAIZ, "trabalho")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

RX_LI = re.compile(r"<li\b[^>]*>([\s\S]*?)</li>", re.I)
RX_TIME = re.compile(r'<time[^>]*datetime="([^"]+)"', re.I)
RX_DUR = re.compile(r"</time>\s*<span[^>]*>([^<]+)</span>", re.I)
RX_TITULO = re.compile(r'<a[^>]*href="/programa/[^"]*"[^>]*>([\s\S]*?)</a>', re.I)
RX_DESC = re.compile(r"<p[^>]*>([\s\S]*?)</p>", re.I)
RX_TAG = re.compile(r"<[^>]+>")
RX_LDJSON = re.compile(r'<script type="application/ld\+json">([\s\S]*?)</script>', re.I)


def texto(s):
    return html.unescape(RX_TAG.sub("", s or "")).strip()


def duracao(s):
    """'3h' -> 10800, '15min' -> 900, '1h30' -> 5400"""
    s = (s or "").lower().replace(" ", "")
    h = re.search(r"(\d+)h", s)
    m = re.search(r"(\d+)(?:min|m)(?!\w)", s) or re.search(r"h(\d+)", s)
    seg = (int(h.group(1)) * 3600 if h else 0) + (int(m.group(1)) * 60 if m else 0)
    return seg or None


def quando(iso):
    try:
        return int(dt.datetime.fromisoformat(iso).timestamp())
    except Exception:
        return None


def ler_pagina(conteudo):
    """[(inicio, fim, titulo, descricao), ...]"""
    progs = []
    for li in RX_LI.findall(conteudo):
        t = RX_TIME.search(li)
        a = RX_TITULO.search(li)
        if not t or not a:
            continue
        ini = quando(t.group(1))
        tit = texto(a.group(1))
        if not ini or not tit:
            continue
        d = RX_DUR.search(li)
        p = RX_DESC.search(li)
        progs.append([ini, None, tit, texto(p.group(1)) if p else "", duracao(d.group(1)) if d else None])
    if not progs:
        progs = reserva_ldjson(conteudo)
    progs.sort(key=lambda x: x[0])
    saida = []
    for i, (ini, fim, tit, desc, dur) in enumerate(progs):
        if not fim:
            prox = progs[i + 1][0] if i + 1 < len(progs) else None
            fim = prox if prox and prox > ini else ini + (dur or 3600)
        saida.append((ini, fim, tit, desc))
    return saida


def reserva_ldjson(conteudo):
    """o 'no ar agora / a seguir' dos dados estruturados da pagina"""
    out = []
    for bloco in RX_LDJSON.findall(conteudo):
        try:
            d = json.loads(bloco)
        except Exception:
            continue
        for ev in (d.get("broadcastEvent") or []) if isinstance(d, dict) else []:
            ini, fim = quando(ev.get("startDate", "")), quando(ev.get("endDate", ""))
            if ini and ev.get("name"):
                out.append([ini, fim, texto(ev["name"]), "", None])
    return out


def baixar(site_id):
    url = f"https://www.guiadetv.com/canal/{site_id}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def xmltv(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y%m%d%H%M%S +0000")


def main():
    entrada = os.path.join(TRABALHO, "canais.channels.xml")
    canais = [(el.get("xmltv_id"), el.get("site_id"))
              for el in ET.parse(entrada).getroot().iter("channel")
              if el.get("site") == "guiadetv.com"]
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>', "<tv>"]
    total = 0
    for xid, sid in canais:
        try:
            progs = ler_pagina(baixar(sid))
        except Exception as e:
            print(f"  guiadetv {sid}: ERRO {e}")
            progs = []
        print(f"  guiadetv {sid}: {len(progs)} programas")
        total += len(progs)
        for ini, fim, tit, desc in progs:
            linhas.append(
                f'<programme start="{xmltv(ini)}" stop="{xmltv(fim)}" channel={quoteattr(xid)}>'
                f"<title lang=\"pt\">{escape(tit)}</title>"
                + (f"<desc lang=\"pt\">{escape(desc)}</desc>" if desc else "")
                + "</programme>")
        time.sleep(0.7)            # devagar: um canal por vez
    linhas.append("</tv>")
    with open(os.path.join(TRABALHO, "guiadetv.com.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print(f"guiadetv: {len(canais)} canais, {total} programas")


if __name__ == "__main__":
    main()
