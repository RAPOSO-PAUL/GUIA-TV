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
    bloco curto (menos de 1h50) tambem — os compactos de 30 min do
    Premiere/SporTV nao entram;
  • Premiere 2..8 mandam o aviso "Hoje a partir das 17:30 - A x B": o
    horario do jogo sai dai.

LIVES DO YOUTUBE (passo 3c, trabalho/youtube.json)
  • so os canais do canais.json com endereco do YouTube (ex.: CazeTV);
  • a live que tem os DOIS times no titulo e o horario do jogo vira a
    PRIMEIRA opcao do jogo, com o codigo daquela live ("youtube":
    {"cazetv": "codigo"} no jogos.json — o app abre aquela live).

SITE jogosdehojenatv.com.br (passo 3b, trabalho/jogosdehoje.json)
  • os jogos do site entram com o HORARIO EXATO e os canais que o site
    diz ("SporTV", "Premiere", "Globo"...). O nome do canal vira a chave do
    app (a mesma regra do guia); so entra canal que o app TEM;
  • "Globo" sem estado vira as Globos do app (globorj, globosp...) e
    "Premiere" sem numero vira os Premiere do app — MAS so quando o guia nao
    achou o canal exato daquele jogo (ex.: "Hoje a partir das..." no
    Premiere 3 ganha do "Premiere" generico do site);
  • o mesmo jogo achado no guia e no site vira UM so (canais somados).

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
import sys
import unicodedata
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import chave  # noqa: E402  (a MESMA regra de chave do guia e do app)

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
        # (os nomes do ESPN ficam no indice SEM hifen/acento: "atletico mg";
        # o apelido "atletico-mg" nunca batia — Atletico Mineiro e Atletico-MG
        # viravam dois jogos)
        self.apelidos = {norm(k): norm(v) for k, v in APELIDOS.items()}
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

    def mesmo_escudo(self, a, b):
        """dois nomes do MESMO time ("Athletico Paranaense" e "Athletico-PR")"""
        def u(nome):
            k = norm(nome)
            return self._direto(k) or self.anteriores.get(k)
        ua = u(a)
        return bool(ua) and ua == u(b)


# palavras que NAO identificam time (nao valem para "parecido")
COMUNS = {"club", "clube", "city", "united", "real", "sport", "sporting", "atletico",
          "athletic", "esporte", "futebol", "football", "deportivo", "internacional",
          "racing", "olympique", "borussia", "saint", "santa", "sao", "san", "unidos"}


# ---------------------------------------------------------------------
#  AS LIVES DO YOUTUBE (passo 3c, trabalho/youtube.json)
# ---------------------------------------------------------------------

def ler_youtube():
    try:
        d = json.load(open(os.path.join(RAIZ, "trabalho", "youtube.json"), encoding="utf-8"))
        return d.get("canais") or {}
    except Exception:
        return {}


def time_no_titulo(nome, palavras_titulo):
    """o time aparece no titulo da live? ("Athletico-PR" em "ATHLETICO PARANAENSE X ...")"""
    p = norm(nome).split()
    if not p:
        return False
    if set(p) <= palavras_titulo:
        return True
    fortes = {w for w in p if len(w) >= 4 and w not in COMUNS}
    return bool(fortes) and fortes <= palavras_titulo


def ligar_youtube(jogos, canais_yt, agora):
    """
    A live do YouTube do jogo (canal do canais.json) vira a PRIMEIRA opcao.
    Precisa ter os DOIS times no titulo da live e o horario bater: live
    agendada ate 3 h antes/depois do jogo, ou live no ar com o jogo no
    ar (ou comecando em ate 1 h).
    """
    ligados = []
    for j in jogos:
        for k, c in canais_yt.items():
            for ev in c.get("eventos") or []:
                palavras = set(norm(ev.get("titulo") or "").split())
                if not (time_no_titulo(j["casa"], palavras) and time_no_titulo(j["fora"], palavras)):
                    continue
                if ev.get("ao_vivo"):
                    if not (j["inicio"] - 3600 <= agora <= j["fim"]):
                        continue
                elif ev.get("inicio") and abs(int(ev["inicio"]) - j["inicio"]) > 3 * 3600:
                    continue
                j.setdefault("youtube", {})[k] = ev["video_id"]
                if k in j["canais"]:
                    j["canais"].remove(k)
                j["canais"].insert(0, k)
                ligados.append(f"{j['casa']} x {j['fora']} -> {c.get('nome', k)} ({ev['video_id']})")
                break
    return ligados


# ---------------------------------------------------------------------
#  O SITE jogosdehojenatv.com.br
# ---------------------------------------------------------------------

def ler_site():
    try:
        d = json.load(open(os.path.join(RAIZ, "trabalho", "jogosdehoje.json"), encoding="utf-8"))
        return d.get("jogos") or []
    except Exception:
        return []


def chaves_validas(guia):
    """as chaves dos canais do APP (mapa do passo 1) + as do guia"""
    validas = set((guia.get("canais") or {}).keys())
    try:
        validas |= set(json.load(open(os.path.join(RAIZ, "trabalho", "mapa.json"), encoding="utf-8")).keys())
    except Exception:
        pass
    return validas


# nome do canal no site -> nome como o app chama (quando muda)
CANAIS_DO_SITE = {
    "ge tv": "", "youtube": "", "premiere play": "premiere", "sportv play": "",
    "globoplay": "", "tv globo": "globo", "rede globo": "globo",
    "espn 1": "espn", "band sports": "bandsports", "tnt sports": "tnt",
    "hbo max": "max", "amazon prime video": "prime video", "caze tv": "cazetv",
}


def canais_do_site(nomes, validas):
    """
    ["SporTV", "Globo", "Premiere"] -> (["sportv"], [("globo", [globorj, globosp]),
                                                      ("premiere", [premiere, premiere2...])])
    especificos = canal exato; genericos = familia (so entra se o guia nao
    tiver o canal exato daquele jogo)
    """
    especificos, genericos = [], []
    for nome in nomes or []:
        n = CANAIS_DO_SITE.get(norm(nome), nome)
        if not n:
            continue
        k = chave(n)
        if not k:
            continue
        if k == "premiere":
            fam = sorted((v for v in validas if re.fullmatch(r"premiere\d*", v)),
                         key=lambda v: (len(v), v))
            if fam:
                genericos.append(("premiere", fam))
            continue
        if k in validas:
            if k not in especificos:
                especificos.append(k)
            continue
        # "Globo" -> globorj, globosp...; "Band" -> bandrj... (sigla de estado no fim)
        regionais = sorted(v for v in validas if v.startswith(k) and re.fullmatch(r"[a-z]{2}", v[len(k):]))
        if regionais:
            genericos.append((k, regionais))
    return especificos, genericos


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


def achar_jogos(guia, escudos, agora, do_site=()):
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
                "canais": [k_canal], "genericos": [],
                "campeonato": campeonato_de(titulo, categoria),
                "exato": bool(m),
            })

    # OS JOGOS DO SITE jogosdehojenatv (horario exato, canais do site)
    validas = chaves_validas(guia)
    for s in do_site:
        try:
            ini = int(s["inicio"])
            casa, fora = str(s["casa"]).strip(), str(s["fora"]).strip()
        except Exception:
            continue
        if not casa or not fora:
            continue
        esp, gen = canais_do_site(s.get("canais"), validas)
        if not esp and not gen:
            continue                                   # nao passa em canal do app
        candidatos.append({
            "casa": casa, "fora": fora, "ini": ini, "fim": ini + DURACAO_PADRAO,
            "canais": esp, "genericos": gen,
            "campeonato": str(s.get("campeonato") or "").strip(),
            "exato": True,
        })

    # o MESMO jogo em varios canais vira um so — mesmo com o nome um pouco
    # diferente de um site para outro ("CS Maritimo" e "Maritimo")
    def mesmo_time(a, b):
        a, b = set(norm(a).split()), set(norm(b).split())
        if not a or not b:
            return False
        menor = a if len(a) <= len(b) else b
        return a == b or ((a <= b or b <= a) and len("".join(menor)) >= 3)

    def mesmo_time_ou_escudo(a, b):
        return mesmo_time(a, b) or escudos.mesmo_escudo(a, b)

    def parecido(a, b):
        """um time com o nome em lingua diferente ("Bayern de Munique" e
        "Bayern München"): divide uma palavra forte (4+ letras)"""
        pa = {w for w in norm(a).split() if len(w) >= 4 and w not in COMUNS}
        pb = {w for w in norm(b).split() if len(w) >= 4 and w not in COMUNS}
        return bool(pa & pb)

    def mesmo_jogo(j, c):
        t = mesmo_time_ou_escudo
        for x, y in (("casa", "fora"), ("fora", "casa")):
            # os dois times batem
            if t(j["casa"], c[x]) and t(j["fora"], c[y]):
                return True
            # um bate certinho e o outro e parecido (site em ingles/alemao,
            # guia em portugues: "FC Augsburg x Bayern München" e
            # "Augsburg x Bayern de Munique")
            if (t(j["casa"], c[x]) and parecido(j["fora"], c[y])) or \
                    (t(j["fora"], c[y]) and parecido(j["casa"], c[x])):
                return True
        return False

    jogos = []
    for c in sorted(candidatos, key=lambda x: x["ini"]):
        alvo = next((j for j in jogos if mesmo_jogo(j, c) and abs(j["_ini0"] - c["ini"]) <= JUNTAR_ATE), None)
        if alvo is None:
            jogos.append({"_ini0": c["ini"], "_inis": [c["ini"]], "_exato": None,
                          "casa": c["casa"], "fora": c["fora"], "campeonato": c["campeonato"],
                          "fim": c["fim"], "canais": list(c["canais"]), "genericos": list(c["genericos"])})
            alvo = jogos[-1]
        else:
            # fica o nome mais curto ("Maritimo" e nao "CS Maritimo")
            # (primeiro descobre se o outro veio na MESMA ordem ou invertido;
            # troca o nome so quando e o mesmo time com certeza)
            t = mesmo_time_ou_escudo
            direto = (t(alvo["casa"], c["casa"]) or t(alvo["fora"], c["fora"]) or
                      parecido(alvo["casa"], c["casa"]) or parecido(alvo["fora"], c["fora"]))
            par = {"casa": c["casa"], "fora": c["fora"]} if direto else {"casa": c["fora"], "fora": c["casa"]}
            for lado in ("casa", "fora"):
                outro = par[lado]
                if t(alvo[lado], outro) and len(outro) < len(alvo[lado]):
                    alvo[lado] = outro
            alvo["_inis"].append(c["ini"])
            alvo["fim"] = max(alvo["fim"], c["fim"])
            for k in c["canais"]:
                if k not in alvo["canais"]:
                    alvo["canais"].append(k)
            alvo["genericos"] += c["genericos"]
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
        # "Globo"/"Premiere" do site sem o canal exato: so quando o guia nao
        # achou nenhum canal daquela familia para este jogo
        canais = list(j["canais"])
        for fam, ks in j["genericos"]:
            if not any(k.startswith(fam) for k in canais):
                canais += [k for k in ks if k not in canais]
        if not canais:
            continue
        saida.append({
            "id": f"{norm(j['casa']).replace(' ', '-')}-x-{norm(j['fora']).replace(' ', '-')}-{ini}",
            "casa": j["casa"], "fora": j["fora"],
            "escudo_casa": escudos.url(j["casa"]), "escudo_fora": escudos.url(j["fora"]),
            "campeonato": j["campeonato"],
            "inicio": ini, "fim": max(j["fim"], ini + 60 * 60),
            "canais": canais,
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
    do_site = ler_site()
    jogos = achar_jogos(guia, escudos, agora, do_site)
    canais_yt = ler_youtube()
    ligados_yt = ligar_youtube(jogos, canais_yt, agora)

    with open(os.path.join(RAIZ, "jogos.json"), "w", encoding="utf-8") as f:
        json.dump({"versao": 1, "gerado": agora, "jogos": jogos}, f, ensure_ascii=False, separators=(",", ":"))

    # ---- relatorio ----
    linhas = ["", "## Jogos de futebol (jogos.json)", "",
              f"{len(jogos)} jogo(s) ao vivo de hoje e amanhã "
              f"(site jogosdehojenatv: {len(do_site)} jogo(s) lido(s)).", ""]
    if jogos:
        linhas += ["| Quando (Brasília) | Jogo | Campeonato | Canais | Escudos |", "|---|---|---|---|---|"]
        for j in jogos:
            q = dt.datetime.fromtimestamp(j["inicio"], BRT)
            esc = ("ok" if j["escudo_casa"] and j["escudo_fora"] else
                   "falta " + " e ".join(n for n, u in ((j["casa"], j["escudo_casa"]),
                                                        (j["fora"], j["escudo_fora"])) if not u))
            linhas.append(f"| {q:%d/%m %H:%M} | {j['casa']} x {j['fora']} | {j['campeonato'] or '—'} | "
                          f"{', '.join(j['canais'])} | {esc} |")
    if canais_yt:
        linhas += ["", f"**Lives do YouTube** ({', '.join(c.get('nome', k) for k, c in canais_yt.items())}):", ""]
        linhas += [f"- {x}" for x in ligados_yt] or ["- nenhum jogo da grade nas lives de agora"]
    if escudos.sem_escudo:
        linhas += ["", "**Times sem escudo** — coloque no `escudos.json` "
                   "(`\"escudos\": {\"Nome do time\": \"https://.../escudo.png\"}`):", ""]
        linhas += [f"- {n}" for n in sorted(escudos.sem_escudo)]
    with open(os.path.join(RAIZ, "relatorio.md"), "a", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print(f"jogos.json: {len(jogos)} jogos, {len(escudos.sem_escudo)} times sem escudo")


if __name__ == "__main__":
    main()
