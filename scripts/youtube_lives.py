"""
PASSO 3c — AS LIVES DO YOUTUBE DOS CANAIS DO APP.

So os canais do canais.json que tem endereco do YouTube (ex.: CazeTV com
"url": "https://www.youtube.com/@CazeTV"). Para cada um, olha no proprio
YouTube o que esta AO VIVO e o que esta AGENDADO — o mesmo jeito do addon
AO VIVO do Kodi (paginas /streams, /featured e /live do canal) — e grava:

    trabalho/youtube.json
      {"gerado": ts,
       "canais": {"cazetv": {"nome": "CazéTV", "url": "https://www.youtube.com/@CazeTV",
                             "eventos": [{"video_id": "abc123xyz00",
                                          "titulo": "BRASIL x ARGENTINA | AMISTOSO",
                                          "inicio": 1791700000,    <- 0 = ja ao vivo
                                          "ao_vivo": true}, ...]}}}

ATENCAO: o robo roda nos EUA e o YouTube ESCONDE dele as lives que so
passam no Brasil (ex.: CazeTV com Premier League). Por isso o APP tambem
procura, no aparelho (YouTubeAoVivo.ligar) — aqui ficam as que o robo ve.

O passo 4 (jogos.py) procura os dois times de cada jogo nos titulos: achou,
o canal do YouTube vira a PRIMEIRA opcao daquele jogo, com o codigo daquela
live (a CazeTV tem varias lives ao mesmo tempo em dia de muitos jogos).

Se o YouTube nao responder, o passo 4 segue sem as lives (nada quebra).
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import baixar_json, chave  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "trabalho", "youtube.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
LIMITE_HTML = 3 * 1024 * 1024
TEMPO_LIMITE = 20

# partes da pagina que sao RECOMENDACAO (videos de outros canais): nao entram
CAIXAS_RECOMENDACAO = frozenset((
    "secondaryResults", "watchNextSecondaryResultsRenderer", "watchNextEndScreenRenderer",
    "compactVideoRenderer", "compactRadioRenderer", "endScreenVideoRenderer",
    "playerOverlayRenderer", "playlistPanelRenderer", "playlistPanelVideoRenderer",
    "engagementPanels", "relatedChipCloudRenderer", "itemSectionRenderer_related",
    "shortsLockupViewModel", "reelShelfRenderer", "horizontalCardListRenderer",
    "channelFeaturedContentRenderer_related", "gridChannelRenderer", "channelRenderer",
    "miniChannelRenderer", "expandedShelfContentsRenderer_channels",
))
RE_CANONICA = re.compile(r'<link\s+rel="canonical"\s+href="[^"]*?/channel/(UC[\w-]{20,})"')
RE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})")
MARCAS_BREVE = ('"style":"UPCOMING"', '"iconType":"UPCOMING"', '"upcomingEventData"', '"text":"EM BREVE"')
MARCAS_VIVO = ('"style":"LIVE"', '"iconType":"LIVE"', '"isLiveNow":true', '"text":"AO VIVO"',
               "BADGE_STYLE_TYPE_LIVE_NOW", "THUMBNAIL_OVERLAY_BADGE_STYLE_LIVE")


def baixar(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Cookie": "CONSENT=YES+cb; SOCS=CAI"})
    with urllib.request.urlopen(req, timeout=TEMPO_LIMITE) as r:
        return r.read(LIMITE_HTML).decode("utf-8", "ignore")


def extrair_json(html, marcador):
    """o objeto JSON que vem depois de 'marcador =' na pagina"""
    pos = -1
    for m in re.finditer(re.escape(marcador) + r'["\]]?\s*=\s*', html):
        pos = m.end()
        break
    if pos < 0:
        pos = html.find(marcador)
    if pos < 0:
        return None
    inicio = html.find("{", pos)
    if inicio < 0:
        return None
    nivel, texto, escapado = 0, False, False
    for i in range(inicio, min(len(html), inicio + 4_000_000)):
        c = html[i]
        if texto:
            if escapado:
                escapado = False
            elif c == "\\":
                escapado = True
            elif c == '"':
                texto = False
            continue
        if c == '"':
            texto = True
        elif c == "{":
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel == 0:
                try:
                    return json.loads(html[inicio:i + 1])
                except Exception:
                    return None
    return None


def iso_para_ts(texto):
    m = RE_ISO.search(str(texto or ""))
    if not m:
        return 0
    import calendar
    ts = calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0))
    fuso = re.search(r"([+-])(\d{2}):?(\d{2})$", str(texto).strip())
    if fuso:
        d = int(fuso.group(2)) * 3600 + int(fuso.group(3)) * 60
        ts = ts - d if fuso.group(1) == "+" else ts + d
    return ts


def id_do_no(no):
    v = no.get("videoId")
    if isinstance(v, str) and len(v) == 11:
        return v
    c = no.get("contentId")
    if isinstance(c, str) and len(c) == 11 and "VIDEO" in str(no.get("contentType") or "").upper():
        return c
    return None


def titulo_do_no(no):
    try:
        t = no.get("title") or {}
        if isinstance(t, dict):
            if t.get("simpleText"):
                return t["simpleText"]
            if t.get("content"):
                return t["content"]
            runs = t.get("runs") or []
            if runs and isinstance(runs[0], dict):
                return "".join(r.get("text", "") for r in runs if isinstance(r, dict))
        meta = ((no.get("metadata") or {}).get("lockupMetadataViewModel") or {}).get("title") or {}
        if meta.get("content"):
            return meta["content"]
    except Exception:
        pass
    return ""


def selos(no):
    s = []
    try:
        for o in no.get("thumbnailOverlays") or []:
            st = (o or {}).get("thumbnailOverlayTimeStatusRenderer") or {}
            if st.get("style"):
                s.append(str(st["style"]).upper())
            if (st.get("text") or {}).get("simpleText"):
                s.append(str(st["text"]["simpleText"]).upper())
        for b in no.get("badges") or []:
            mb = (b or {}).get("metadataBadgeRenderer") or {}
            if mb.get("style"):
                s.append(str(mb["style"]).upper())
            if mb.get("label"):
                s.append(str(mb["label"]).upper())
        ov = ((no.get("contentImage") or {}).get("thumbnailViewModel") or {}).get("overlays") or []
        for o in ov:
            for b in ((o or {}).get("thumbnailOverlayBadgeViewModel") or {}).get("thumbnailBadges") or []:
                bv = (b or {}).get("thumbnailBadgeViewModel") or {}
                if bv.get("badgeStyle"):
                    s.append(str(bv["badgeStyle"]).upper())
                if bv.get("text"):
                    s.append(str(bv["text"]).upper())
    except Exception:
        pass
    return s


def classificar(no):
    """'live', 'breve' ou None"""
    try:
        if no.get("upcomingEventData"):
            return "breve"
        t = " ".join(selos(no))
        if "UPCOMING" in t or "EM BREVE" in t:
            return "breve"
        if "LIVE" in t or "AO VIVO" in t or "DIRETO" in t:
            return "live"
        for campo in ("viewCountText", "shortViewCountText"):
            v = no.get(campo) or {}
            txt = v.get("simpleText") or "".join(r.get("text", "") for r in v.get("runs") or []
                                                if isinstance(r, dict))
            if "ASSISTINDO" in txt.upper() or "WATCHING" in txt.upper():
                return "live"
        blob = json.dumps(no, ensure_ascii=False, separators=(",", ":"))
        if any(m in blob for m in MARCAS_BREVE):
            return "breve"
        if any(m in blob for m in MARCAS_VIVO):
            return "live"
    except Exception:
        pass
    return None


def dono_diferente(no, dono):
    """video de OUTRO canal (recomendacao): fica de fora"""
    if not dono:
        return False
    try:
        blob = json.dumps(no, ensure_ascii=False, separators=(",", ":"))
        for campo in ("shortBylineText", "longBylineText", "ownerText"):
            i = blob.find('"%s"' % campo)
            if i < 0:
                continue
            m = re.search(r'"browseId":"(UC[\w-]{20,})"', blob[i:i + 1200])
            if m and m.group(1) != dono:
                return True
    except Exception:
        pass
    return False


def coletar(no, achados, vistos, dono):
    try:
        if isinstance(no, dict):
            vid = id_do_no(no)
            if vid and vid not in vistos and not dono_diferente(no, dono):
                tipo = classificar(no)
                if tipo:
                    vistos.add(vid)
                    inicio = 0
                    ev = no.get("upcomingEventData") or {}
                    if isinstance(ev, dict) and ev.get("startTime"):
                        inicio = int(ev["startTime"])
                    achados[tipo].append({"video_id": vid, "titulo": titulo_do_no(no), "inicio": inicio})
            for k, v in no.items():
                if k in CAIXAS_RECOMENDACAO:
                    continue
                coletar(v, achados, vistos, dono)
        elif isinstance(no, list):
            for v in no:
                coletar(v, achados, vistos, dono)
    except Exception:
        pass


def analisar_canal(html):
    m = RE_CANONICA.search(html)
    dono = m.group(1) if m else ""
    dados = extrair_json(html, "ytInitialData")
    achados = {"live": [], "breve": []}
    if dados:
        coletar(dados, achados, set(), dono)
    return achados


def analisar_live(html):
    """pagina /live: o video que abre (ao vivo ou agendado)"""
    pr = extrair_json(html, "ytInitialPlayerResponse") or {}
    vd = pr.get("videoDetails") or {}
    vid = vd.get("videoId")
    if not vid:
        return None
    ps = pr.get("playabilityStatus") or {}
    if vd.get("isUpcoming") is True or ps.get("status") == "LIVE_STREAM_OFFLINE":
        inicio = 0
        try:
            slate = ((ps.get("liveStreamability") or {}).get("liveStreamabilityRenderer") or {}) \
                .get("offlineSlate") or {}
            inicio = int((slate.get("liveStreamOfflineSlateRenderer") or {}).get("scheduledStartTime") or 0)
        except Exception:
            pass
        if not inicio:
            det = ((pr.get("microformat") or {}).get("playerMicroformatRenderer") or {}) \
                .get("liveBroadcastDetails") or {}
            inicio = iso_para_ts(det.get("startTimestamp"))
        return "breve", {"video_id": vid, "titulo": vd.get("title", ""), "inicio": inicio}
    if vd.get("isLive") is True:
        return "live", {"video_id": vid, "titulo": vd.get("title", ""), "inicio": 0}
    return None


def paginas(url):
    """endereco do canal no canais.json -> as paginas que mostram as lives"""
    u = urllib.parse.urlparse(url.strip())
    partes = [p for p in u.path.split("/") if p]
    base = None
    if partes and partes[0].startswith("@"):
        base = "https://www.youtube.com/" + urllib.parse.quote(partes[0], safe="@")
    elif len(partes) >= 2 and partes[0] in ("channel", "c", "user"):
        base = "https://www.youtube.com/%s/%s" % (partes[0], partes[1])
    if not base:
        return []
    # a PAGINA INICIAL primeiro: a CazeTV mostra a live ali, no destaque
    return [base, base + "/streams", base + "/live"]


# canais conhecidos (se a pagina nao disser o codigo do canal)
CODIGOS_CONHECIDOS = {"@cazetv": "UCZiYbVptd3PVPf4f6eR6UaQ"}
RE_CODIGO = (RE_CANONICA,
             re.compile(r'"externalId"\s*:\s*"(UC[\w-]{20,})"'),
             re.compile(r'<meta\s+itemprop="(?:channelId|identifier)"\s+content="(UC[\w-]{20,})"'),
             re.compile(r'"browseId"\s*:\s*"(UC[\w-]{20,})"'))
RX_REPRISE = re.compile(r"melhores momentos|gols d[aoe]|compacto|resumo|p[oó]s[- ]jogo|"
                        r"reprise|highlights|react|jogo completo", re.I)


def codigo_do_canal(url, htmls):
    """UC... do canal: do endereco, das paginas baixadas ou da lista conhecida"""
    partes = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
    if len(partes) >= 2 and partes[0] == "channel" and partes[1].startswith("UC"):
        return partes[1]
    for html in htmls:
        for rx in RE_CODIGO:
            m = rx.search(html)
            if m:
                return m.group(1)
    if partes and partes[0].lower() in CODIGOS_CONHECIDOS:
        return CODIGOS_CONHECIDOS[partes[0].lower()]
    return None


def pelo_rss(codigo, dias=3):
    """
    O feed do canal (videos.xml): as ultimas lives/videos, com titulo. Live
    agendada aparece aqui assim que o canal agenda. So os dos ultimos dias
    e sem cara de reprise (melhores momentos, gols, pos-jogo...).
    """
    import xml.etree.ElementTree as ET
    xml = baixar("https://www.youtube.com/feeds/videos.xml?channel_id=" + codigo)
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    raiz = ET.fromstring(xml)
    limite = time.time() - dias * 86400
    saida = []
    for e in raiz.findall("a:entry", ns):
        vid = (e.findtext("yt:videoId", "", ns) or "").strip()
        titulo = (e.findtext("a:title", "", ns) or "").strip()
        quando = iso_para_ts(e.findtext("a:published", "", ns))
        if len(vid) != 11 or not titulo or (quando and quando < limite) or RX_REPRISE.search(titulo):
            continue
        saida.append({"video_id": vid, "titulo": titulo, "inicio": 0})
    return saida


def pela_api(codigo):
    """a mesma pagina inicial, pedida como os aplicativos pedem (JSON puro)"""
    corpo = json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": "2.20250925.01.00",
                                               "hl": "pt", "gl": "BR"}},
                        "browseId": codigo}).encode()
    req = urllib.request.Request("https://www.youtube.com/youtubei/v1/browse?prettyPrint=false",
                                 data=corpo, headers={"User-Agent": UA, "Content-Type": "application/json",
                                                      "Accept-Language": "pt-BR,pt;q=0.9",
                                                      "Cookie": "CONSENT=YES+cb; SOCS=CAI",
                                                      "Origin": "https://www.youtube.com"})
    with urllib.request.urlopen(req, timeout=TEMPO_LIMITE) as r:
        dados = json.loads(r.read(LIMITE_HTML).decode("utf-8", "ignore"))
    achados = {"live": [], "breve": []}
    coletar(dados, achados, set(), codigo)
    return achados


def diagnostico(pg, html):
    """o que a pagina trouxe (aparece no log do passo 3c)"""
    t = re.search(r"<title>(.*?)</title>", html, re.S)
    marcas = [m for m in ("consent.youtube.com", "confirm you", "not a bot", "nao e um robo",
                          "não é um robô", "/sorry/") if m in html.lower()]
    return (f"{pg.split('youtube.com', 1)[-1] or '/'}: {len(html) // 1024} KB, "
            f"ytInitialData={'sim' if 'ytInitialData' in html else 'NAO'}, "
            f"player={'sim' if 'ytInitialPlayerResponse' in html else 'nao'}, "
            f"titulo={(t.group(1).strip()[:50] if t else '?')!r}"
            + (f", AVISO: {', '.join(marcas)}" if marcas else ""))


def eh_youtube(url):
    try:
        h = (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return h in ("youtube.com", "www.youtube.com", "m.youtube.com")


def canais_youtube(raiz):
    """os canais do canais.json com endereco de canal do YouTube"""
    if isinstance(raiz, dict):
        cats = raiz.get("categorias") or raiz.get("categories") or []
        if not cats and isinstance(raiz.get("canais"), list):
            cats = [{"canais": raiz["canais"]}]
    else:
        cats = raiz if isinstance(raiz, list) else []
    saida = {}
    for cat in cats:
        if not isinstance(cat, dict):
            continue
        for c in cat.get("canais") or cat.get("channels") or cat.get("itens") or []:
            if not isinstance(c, dict):
                continue
            nome = next((c[k].strip() for k in ("nome", "name", "titulo", "title")
                         if isinstance(c.get(k), str) and c[k].strip()), "")
            url = next((c[k].strip() for k in ("stream", "stream_url", "m3u8", "direto", "embed",
                                                "iframe", "url", "link", "player")
                        if isinstance(c.get(k), str) and c[k].strip()), "")
            if not nome or not eh_youtube(url) or not paginas(url):
                continue
            epg = c.get("epg") if isinstance(c.get("epg"), str) and c["epg"].strip() else None
            k = chave(epg or nome)
            codigo = next((c[x].strip() for x in ("youtube_id", "channel_id")
                           if isinstance(c.get(x), str) and c[x].strip().startswith("UC")), None)
            saida.setdefault(k, {"nome": nome, "url": url, "codigo": codigo})
    return saida


def main():
    cfg = json.load(open(os.path.join(RAIZ, "config.json"), encoding="utf-8"))
    try:
        canais = canais_youtube(baixar_json(cfg["canais_url"]))
    except Exception as e:
        print(f"canais.json nao baixou ({e}) — sem lives do YouTube")
        return
    if not canais:
        print("nenhum canal do YouTube no canais.json")
        return
    saida = {}
    for k, c in canais.items():
        somados = {"live": [], "breve": []}
        vistos = set()
        erros = []
        htmls = []
        notas = []

        def somar(achados):
            for tipo in ("live", "breve"):
                for ev in achados.get(tipo) or []:
                    if ev["video_id"] not in vistos:
                        vistos.add(ev["video_id"])
                        somados[tipo].append(ev)

        for pg in paginas(c["url"]):
            try:
                html = baixar(pg)
                htmls.append(html)
                notas.append(diagnostico(pg, html))
                if pg.endswith("/live"):
                    r = analisar_live(html)
                    achados = {"live": [], "breve": []}
                    if r:
                        achados[r[0]].append(r[1])
                else:
                    achados = analisar_canal(html)
                somar(achados)
            except Exception as e:
                erros.append(f"{pg.split('youtube.com', 1)[-1] or '/'}: {e}")
            time.sleep(0.6)

        # OUTROS DOIS CAMINHOS, para quando a pagina vem sem a lista (o
        # YouTube as vezes manda pagina "vazia" para servidor):
        codigo = c.get("codigo") or codigo_do_canal(c["url"], htmls)
        recentes = []
        if codigo:
            try:
                antes = len(vistos)
                somar(pela_api(codigo))
                notas.append(f"api: {len(vistos) - antes} live(s) a mais")
            except Exception as e:
                erros.append(f"api: {e}")
            try:
                recentes = [ev for ev in pelo_rss(codigo) if ev["video_id"] not in vistos]
                notas.append(f"rss: {len(recentes)} video(s) recente(s)")
            except Exception as e:
                erros.append(f"rss: {e}")
        else:
            erros.append("codigo do canal (UC...) nao achado — ponha \"youtube_id\" no canal")

        eventos = [dict(e, ao_vivo=True, inicio=0) for e in somados["live"]] + \
                  [dict(e, ao_vivo=False) for e in somados["breve"]] + \
                  [dict(e, ao_vivo=False, recente=True) for e in recentes]
        saida[k] = {"nome": c["nome"], "url": c["url"], "eventos": eventos}
        print(f"{c['nome']} ({codigo or 'sem codigo'}): {len(somados['live'])} ao vivo, "
              f"{len(somados['breve'])} agendada(s), {len(recentes)} recente(s) pelo feed")
        for n in notas:
            print(f"   · {n}")
        for e in erros:
            print(f"   ! {e}")
        for e in eventos:
            quando = "AO VIVO" if e["ao_vivo"] else "feed" if e.get("recente") else (
                dt.datetime.fromtimestamp(e["inicio"], dt.timezone(dt.timedelta(hours=-3))).strftime("%d/%m %H:%M")
                if e["inicio"] else "agendada")
            print(f"   [{quando}] {e['titulo'][:100]}  ({e['video_id']})")
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump({"gerado": int(time.time()), "canais": saida}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                      # nunca derruba o robo
        print(f"lives do YouTube falharam: {e}", file=sys.stderr)
