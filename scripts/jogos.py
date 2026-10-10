"""
PASSO 4 — A GRADE DE FUTEBOL (jogos.json).

Le o guia.json que o passo 3 acabou de gravar e acha os JOGOS DE FUTEBOL
AO VIVO de hoje e amanha (horario de Brasilia): "CRB x Nautico" no canal
tal, as tantas horas. O mesmo jogo em varios canais vira UM jogo com a
lista de canais. Para cada time busca o ESCUDO.

  jogos.json    -> o que o app baixa (aba FUTEBOL)
  relatorio.md  -> ganha a secao "Jogos de futebol" no fim (o que foi
                   achado e os times que ficaram sem escudo)

COMO DECIDE
  • so futebol: o canal e Premiere, OU a categoria/titulo fala de futebol
    (Campeonato Brasileiro, Copa do Brasil, Amistoso de Futebol...), OU um
    dos times existe na base de futebol do ESPN. NBA, NFL, volei,
    futevolei, boxe etc. ficam de fora;
  • so AO VIVO: reprise (VT, compacto, melhores momentos) fica de fora, e
    bloco curto (menos de 80 min) tambem — os compactos de 30 min do
    Premiere/SporTV nao entram;
  • Premiere 2..8 mandam o aviso "Hoje a partir das 17:30 - A x B": o
    horario do jogo sai dai.

ESCUDOS
  1) escudos.json (na raiz do repositorio) — o que voce colocar la manda;
  2) a base publica do ESPN (Brasileirao A/B/C, Copa do Brasil,
     Libertadores, Sul-Americana, principais ligas da Europa, Arabia...);
  3) selecoes: a bandeira do pais pelo ESPN;
  4) sem escudo: o app mostra as iniciais do time num escudo generico.
"""
import datetime as dt
import json
import os
import re
import unicodedata
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRT = dt.timezone(dt.timedelta(hours=-3))

# JOGO AO VIVO no guia tem 2 h ou mais (90 min de bola + intervalo + pre-jogo).
# Bloco de 1 h / 1h30 e REPRISE (o Premiere passa "Premiere Retro" e jogos
# antigos de 30, 60 e 90 min com o mesmo nome do jogo). Nenhum ao vivo do
# guia tem menos de 2 h; 110 min deixa uma folga.
DURACAO_MINIMA = 110 * 60
DURACAO_PADRAO = 115 * 60         # quando so se sabe o inicio (Premiere 2..8)
JUNTAR_ATE = 3 * 3600             # mesmo jogo em canais diferentes: inicio ate 3 h de diferenca

# ligas do ESPN de onde vem os escudos (a ORDEM conta: Brasil primeiro)
LIGAS_ESPN = [
    "bra.1", "bra.2", "bra.3", "bra.copa_do_brazil",
    "conmebol.libertadores", "conmebol.sudamericana",
    "arg.1", "uru.1", "col.1", "chi.1", "mex.1", "usa.1",
    "eng.1", "eng.2", "esp.1", "ita.1", "ger.1", "fra.1", "por.1", "ned.1",
    "tur.1", "sco.1", "bel.1", "ksa.1",
    "uefa.champions", "uefa.europa", "uefa.europa.conf",
]
URL_ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/{}/teams?limit=200"
URL_BANDEIRA = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png"

# selecoes (nome no guia, sem acento e minusculo) -> codigo do ESPN
SELECOES = {
    "brasil": "bra", "argentina": "arg", "uruguai": "uru", "paraguai": "par",
    "chile": "chi", "colombia": "col", "peru": "per", "equador": "ecu",
    "venezuela": "ven", "bolivia": "bol", "mexico": "mex", "estados unidos": "usa",
    "eua": "usa", "canada": "can", "costa rica": "crc", "panama": "pan",
    "jamaica": "jam", "honduras": "hon", "alemanha": "ger", "franca": "fra",
    "espanha": "esp", "portugal": "por", "italia": "ita", "inglaterra": "eng",
    "holanda": "ned", "paises baixos": "ned", "belgica": "bel", "croacia": "cro",
    "suica": "sui", "dinamarca": "den", "suecia": "swe", "noruega": "nor",
    "polonia": "pol", "austria": "aut", "republica tcheca": "cze", "turquia": "tur",
    "escocia": "sco", "pais de gales": "wal", "irlanda": "irl", "servia": "srb",
    "ucrania": "ukr", "grecia": "gre", "hungria": "hun", "romenia": "rou",
    "japao": "jpn", "coreia do sul": "kor", "australia": "aus", "arabia saudita": "ksa",
    "catar": "qat", "ira": "irn", "china": "chn", "india": "ind",
    "nova zelandia": "nzl", "marrocos": "mar", "senegal": "sen", "nigeria": "nga",
    "camaroes": "cmr", "gana": "gha", "egito": "egy", "tunisia": "tun",
    "argelia": "alg", "africa do sul": "rsa", "costa do marfim": "civ",
    "benin": "ben", "benim": "ben", "mali": "mli", "cabo verde": "cpv", "angola": "ang",
}

# nomes do guia (em portugues) -> como o ESPN chama o time
APELIDOS = {
    "bayern de munique": "bayern munich", "inter de milao": "internazionale",
    "inter": "internazionale", "milan": "ac milan", "atletico de madrid": "atletico madrid",
    "paris saint germain": "paris saint-germain", "psg": "paris saint-germain",
    "tottenham": "tottenham hotspur", "newcastle": "newcastle united",
    "west ham": "west ham united", "wolverhampton": "wolverhampton wanderers",
    "wolves": "wolverhampton wanderers", "brighton": "brighton & hove albion",
    "leicester": "leicester city", "leeds": "leeds united", "nottingham forest": "nottingham forest",
    "sporting": "sporting cp", "porto": "fc porto", "cs maritimo": "maritimo",
    "olympique de marselha": "marseille", "marselha": "marseille", "lyon": "lyon",
    "borussia dortmund": "borussia dortmund", "dortmund": "borussia dortmund",
    "leverkusen": "bayer leverkusen", "roma": "as roma", "napoles": "napoli",
    "lazio": "lazio", "sevilha": "sevilla", "betis": "real betis",
    "athletico": "athletico-pr", "athletico paranaense": "athletico-pr",
    "atletico mineiro": "atletico-mg", "atletico goianiense": "atletico-go",
    "america mineiro": "america-mg", "red bull bragantino": "bragantino",
    "vasco da gama": "vasco", "sport recife": "sport",
}

# nao e futebol
RX_NAO_FUTEBOL = re.compile(
    r"\b(nba|wnba|nfl|nhl|mlb|ncaa|boxe|knockout|ufc|mma|volei|futevolei|basquete|"
    r"beisebol|hoquei|tenis|handebol|futsal|futebol americano|rugby|golfe|formula|"
    r"f1|motogp|nascar|ciclismo|atletismo|natacao|sinuca|dardos|esports|poker)\b")
# e futebol
RX_FUTEBOL = re.compile(
    r"futebol|brasileir|copa do brasil|libertadores|sul americana|copa do nordeste|"
    r"copa verde|serie [abcd]\b|premier league|la liga|laliga|bundesliga|ligue 1|"
    r"champions|liga europa|conference league|eliminatoria|copa do mundo|copa america|"
    r"campeonato (ingles|espanhol|italiano|alemao|frances|portugues|neerlandes|holandes|"
    r"saudita|argentino|turco|escoces|belga|uruguaio|mexicano|carioca|paulista|mineiro|"
    r"gaucho|baiano|pernambucano|cearense|paranaense|goiano|catarinense)")
# reprise
RX_REPRISE = re.compile(r"(^|\W)(vt|reprise|compacto|melhores momentos|gols da rodada|"
                        r"reapresentacao|resumo|retro|classicos?|jogo historico|"
                        r"jogos historicos|memoria|reprisado|gravado)(\W|$)")
RX_HOJE = re.compile(r"^\s*hoje\s+a\s+partir\s+das?\s+(\d{1,2})\s*[:h]\s*(\d{2})\s*[-–:]\s*", re.I)
RX_DIA = re.compile(r"^\s*dia\s+\d{1,2}/\d{1,2}\s*[-–:]\s*", re.I)
RX_X = re.compile(r"\s+(?:x|X|vs\.?|VS\.?|versus)\s+")


def sem_acento(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def norm(s):
    """'Atlético-MG' -> 'atletico mg'"""
    s = sem_acento(s).lower().replace("&", " ")
    return " ".join(re.findall(r"[a-z0-9]+", s))


# ---------------------------------------------------------------------
#  ESCUDOS
# ---------------------------------------------------------------------

def baixar_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "guia-tv/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def indice_espn():
    """{nome normalizado: url do escudo} com os times das LIGAS_ESPN"""
    indice = {}
    for liga in LIGAS_ESPN:
        try:
            d = baixar_json(URL_ESPN.format(liga))
        except Exception as e:
            print(f"  escudos: {liga} falhou ({e})")
            continue
        n = 0
        for lg in (d.get("sports") or [{}])[0].get("leagues") or []:
            for item in lg.get("teams") or []:
                t = item.get("team") or {}
                logos = [l.get("href") for l in t.get("logos") or [] if l.get("href")]
                # o primeiro e o escudo normal (o segundo e a versao para fundo escuro)
                logo = logos[0] if logos else (
                    f"https://a.espncdn.com/i/teamlogos/soccer/500/{t['id']}.png" if t.get("id") else "")
                if not logo:
                    continue
                for nome in (t.get("shortDisplayName"), t.get("displayName"), t.get("name"), t.get("location")):
                    k = norm(nome)
                    if k and k not in indice:
                        indice[k] = logo
                n += 1
        print(f"  escudos: {liga} -> {n} times")
    return indice


def carregar_manual():
    """escudos.json: {"escudos": {"Time": "url"}, "apelidos": {"Nome no guia": "nome no ESPN"}}"""
    try:
        d = json.load(open(os.path.join(RAIZ, "escudos.json"), encoding="utf-8"))
    except Exception:
        return {}, {}
    escudos = {norm(k): v for k, v in (d.get("escudos") or {}).items() if isinstance(v, str) and v.strip()}
    apelidos = {norm(k): norm(v) for k, v in (d.get("apelidos") or {}).items() if isinstance(v, str)}
    return escudos, apelidos


class Escudos:
    def __init__(self, indice, manual, apelidos_manuais, anteriores):
        self.indice = indice
        self.manual = manual
        self.apelidos = dict(APELIDOS)
        self.apelidos.update(apelidos_manuais)
        self.anteriores = anteriores          # do jogos.json anterior (se o ESPN falhar)
        self.sem_escudo = set()

    def _clube(self, k):
        """achado SEGURO de clube (nome igual ou apelido) — prova de que e futebol"""
        if k in self.manual:
            return self.manual[k]
        alvo = self.apelidos.get(k, k)
        if alvo in self.indice:
            return self.indice[alvo]
        return None

    def _direto(self, k):
        u = self._clube(k)
        if u:
            return u
        if k in SELECOES:
            return URL_BANDEIRA.format(SELECOES[k])
        return None

    def de_futebol(self, nome):
        # SELECAO NAO CONTA: "Estados Unidos x Espanha" pode ser basquete.
        # Jogo de selecao so entra com categoria/titulo de futebol.
        return self._clube(norm(nome)) is not None

    def url(self, nome):
        k = norm(nome)
        u = self._direto(k)
        if u:
            return u
        # nome parecido, mas so se for UM time so ("CS Maritimo" -> "Maritimo")
        q = set(k.split())
        if q:
            achados = {v for n, v in self.indice.items()
                       if (q <= set(n.split()) or set(n.split()) <= q) and len(n) >= 4}
            if len(achados) == 1:
                return achados.pop()
        if k in self.anteriores:
            return self.anteriores[k]
        self.sem_escudo.add(nome)
        return ""


# ---------------------------------------------------------------------
#  OS JOGOS
# ---------------------------------------------------------------------

def separar_times(titulo):
    """'Futebol Brasileiro Serie B: CRB x Nautico - Ao vivo' -> ('CRB', 'Nautico')"""
    t = titulo.strip()
    if ":" in t:
        # o que vem depois do ultimo ":" que tenha o "x"
        partes = t.split(":")
        for i in range(len(partes) - 1, -1, -1):
            if RX_X.search(partes[i]):
                t = ":".join(partes[i:]).strip()
                break
    lados = RX_X.split(t)
    if len(lados) != 2:
        return None
    a, b = lados[0].strip(" -–"), lados[1].strip(" -–")
    b = re.split(r"\s+[-–]\s+|\s*\(", b)[0].strip()       # "Nautico - Ao vivo" / "Nautico (ao vivo)"
    a = re.split(r"\s*\(", a)[0].strip()
    if not a or not b or len(a) > 40 or len(b) > 40:
        return None
    return a, b


def campeonato_de(titulo, categoria):
    c = (categoria or "").strip()
    if c and norm(c) not in ("futebol", "esporte", "esportes"):
        return c
    if ":" in titulo:
        antes = titulo.split(":")[0].strip()
        if not RX_X.search(antes) and len(antes) <= 50:
            return antes
    return ""


def achar_jogos(guia, escudos, agora):
    candidatos = []
    for k_canal, dados in (guia.get("canais") or {}).items():
        premiere = k_canal.startswith("premiere")
        for p in dados.get("p") or []:
            if len(p) < 3:
                continue
            ini, fim, titulo = p[0], p[1], p[2] or ""
            categoria = p[4] if len(p) > 4 else ""
            texto = norm(titulo + " " + categoria)
            if RX_DIA.match(titulo):
                continue                                   # aviso do dia seguinte (sem horario)
            m = RX_HOJE.match(titulo)
            if m:
                # Premiere 2..8: "Hoje a partir das 17:30 - A x B" (horario de Brasilia)
                dia = dt.datetime.fromtimestamp(ini, BRT).date()
                hh, mm = int(m.group(1)), int(m.group(2))
                ini = int(dt.datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=BRT).timestamp())
                fim = ini + DURACAO_PADRAO
                titulo = titulo[m.end():]
            elif fim - ini < DURACAO_MINIMA:
                continue                                   # compacto / resumo
            if RX_REPRISE.search(texto):
                continue
            if RX_NAO_FUTEBOL.search(texto):
                continue
            times = separar_times(titulo)
            if not times:
                continue
            futebol = premiere or bool(RX_FUTEBOL.search(texto)) or \
                escudos.de_futebol(times[0]) or escudos.de_futebol(times[1])
            if not futebol:
                continue
            candidatos.append({
                "casa": times[0], "fora": times[1], "ini": ini, "fim": fim,
                "canal": k_canal, "campeonato": campeonato_de(titulo, categoria),
                "exato": bool(m),
            })

    # o MESMO jogo em varios canais vira um so — mesmo com o nome um pouco
    # diferente de um site para outro ("CS Maritimo" e "Maritimo")
    def mesmo_time(a, b):
        a, b = set(norm(a).split()), set(norm(b).split())
        if not a or not b:
            return False
        menor = a if len(a) <= len(b) else b
        return a == b or ((a <= b or b <= a) and len("".join(menor)) >= 3)

    def mesmo_jogo(j, c):
        return ((mesmo_time(j["casa"], c["casa"]) and mesmo_time(j["fora"], c["fora"])) or
                (mesmo_time(j["casa"], c["fora"]) and mesmo_time(j["fora"], c["casa"])))

    jogos = []
    for c in sorted(candidatos, key=lambda x: x["ini"]):
        alvo = next((j for j in jogos if mesmo_jogo(j, c) and abs(j["_ini0"] - c["ini"]) <= JUNTAR_ATE), None)
        if alvo is None:
            jogos.append({"_ini0": c["ini"], "_inis": [c["ini"]], "_exato": None,
                          "casa": c["casa"], "fora": c["fora"], "campeonato": c["campeonato"],
                          "fim": c["fim"], "canais": [c["canal"]]})
            alvo = jogos[-1]
        else:
            # fica o nome mais curto ("Maritimo" e nao "CS Maritimo")
            for lado in ("casa", "fora"):
                outro = c[lado] if mesmo_time(alvo[lado], c[lado]) else c["fora" if lado == "casa" else "casa"]
                if len(outro) < len(alvo[lado]):
                    alvo[lado] = outro
            alvo["_inis"].append(c["ini"])
            alvo["fim"] = max(alvo["fim"], c["fim"])
            if c["canal"] not in alvo["canais"]:
                alvo["canais"].append(c["canal"])
            if not alvo["campeonato"] and c["campeonato"]:
                alvo["campeonato"] = c["campeonato"]
        if c["exato"]:
            alvo["_exato"] = c["ini"]

    # hoje e amanha (Brasilia), sem os que ja acabaram
    hoje = dt.datetime.fromtimestamp(agora, BRT).date()
    fim_amanha = int(dt.datetime(hoje.year, hoje.month, hoje.day, tzinfo=BRT).timestamp()) + 2 * 86400
    saida = []
    for j in jogos:
        # inicio: o horario exato do Premiere; senao o canal que entra mais
        # tarde (o mais cedo costuma ser a pre-transmissao), ate 45 min
        inis = sorted(j["_inis"])
        ini = j["_exato"] or (inis[-1] if inis[-1] - inis[0] <= 45 * 60 else inis[0])
        if j["fim"] <= agora or ini >= fim_amanha:
            continue
        saida.append({
            "id": f"{norm(j['casa']).replace(' ', '-')}-x-{norm(j['fora']).replace(' ', '-')}-{ini}",
            "casa": j["casa"], "fora": j["fora"],
            "escudo_casa": escudos.url(j["casa"]), "escudo_fora": escudos.url(j["fora"]),
            "campeonato": j["campeonato"],
            "inicio": ini, "fim": max(j["fim"], ini + 60 * 60),
            "canais": j["canais"],
        })
    saida.sort(key=lambda x: (x["inicio"], x["casa"]))
    return saida


def main():
    agora = int(dt.datetime.now(dt.timezone.utc).timestamp())
    try:
        guia = json.load(open(os.path.join(RAIZ, "guia.json"), encoding="utf-8"))
    except Exception as e:
        print(f"sem guia.json ({e}) — jogos.json nao mudou")
        return
    anteriores = {}
    try:
        for j in json.load(open(os.path.join(RAIZ, "jogos.json"), encoding="utf-8")).get("jogos") or []:
            for lado in ("casa", "fora"):
                if j.get("escudo_" + lado):
                    anteriores[norm(j[lado])] = j["escudo_" + lado]
    except Exception:
        pass

    manual, apelidos = carregar_manual()
    escudos = Escudos(indice_espn(), manual, apelidos, anteriores)
    jogos = achar_jogos(guia, escudos, agora)

    with open(os.path.join(RAIZ, "jogos.json"), "w", encoding="utf-8") as f:
        json.dump({"versao": 1, "gerado": agora, "jogos": jogos}, f, ensure_ascii=False, separators=(",", ":"))

    # ---- relatorio ----
    linhas = ["", "## Jogos de futebol (jogos.json)", "",
              f"{len(jogos)} jogo(s) ao vivo de hoje e amanhã.", ""]
    if jogos:
        linhas += ["| Quando (Brasília) | Jogo | Campeonato | Canais | Escudos |", "|---|---|---|---|---|"]
        for j in jogos:
            q = dt.datetime.fromtimestamp(j["inicio"], BRT)
            esc = ("ok" if j["escudo_casa"] and j["escudo_fora"] else
                   "falta " + " e ".join(n for n, u in ((j["casa"], j["escudo_casa"]),
                                                        (j["fora"], j["escudo_fora"])) if not u))
            linhas.append(f"| {q:%d/%m %H:%M} | {j['casa']} x {j['fora']} | {j['campeonato'] or '—'} | "
                          f"{', '.join(j['canais'])} | {esc} |")
    if escudos.sem_escudo:
        linhas += ["", "**Times sem escudo** — coloque no `escudos.json` "
                   "(`\"escudos\": {\"Nome do time\": \"https://.../escudo.png\"}`):", ""]
        linhas += [f"- {n}" for n in sorted(escudos.sem_escudo)]
    with open(os.path.join(RAIZ, "relatorio.md"), "a", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print(f"jogos.json: {len(jogos)} jogos, {len(escudos.sem_escudo)} times sem escudo")


if __name__ == "__main__":
    main()
