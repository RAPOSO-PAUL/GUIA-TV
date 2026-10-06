"""Funcoes usadas pelos dois scripts do guia."""
import json
import re
import unicodedata
import urllib.request

# Pedacos do nome que NAO mudam o canal: qualidade, numero da fonte (HD1, HD2...)
DESCARTAR = re.compile(r"^(f|u)?hd\d*$|^sd\d*$|^4k$|^h26[45]$|^hevc$|^alt\d*$|^backup$|^br$")


def chave(nome: str) -> str:
    """
    O NOME DO CANAL VIRA UMA CHAVE. A MESMA regra existe no app (data/Guia.kt).

      "SPORTV 2 HD3"         -> "sportv2"
      "ESPN 1 HD2"           -> "espn"        (o " 1" no fim sai)
      "TELECINE ACTION HD1"  -> "telecineaction"
      "Band RJ HD"           -> "bandrj"
      "Disney+"              -> "disneyplus"
    """
    s = unicodedata.normalize("NFD", nome or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"[\(\[].*?[\)\]]", " ", s)          # tira (...) e [...]
    s = s.replace("+", " plus ")
    partes = [p for p in re.split(r"[^a-z0-9]+", s) if p]
    partes = [p for p in partes if not DESCARTAR.match(p)]
    if len(partes) > 1 and partes[-1] == "1":
        partes = partes[:-1]
    return "".join(partes)


def baixar_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "guia-tv/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def texto(o: dict, *nomes):
    for n in nomes:
        v = o.get(n)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def canais_do_app(raiz) -> list:
    """Le o canais.json do app do mesmo jeito que o app le (categorias -> canais)."""
    categorias = []
    if isinstance(raiz, dict):
        if isinstance(raiz.get("categorias"), list):
            categorias = raiz["categorias"]
        elif isinstance(raiz.get("canais"), list):
            categorias = [{"nome": "Canais", "canais": raiz["canais"]}]
    elif isinstance(raiz, list):
        categorias = raiz
    saida = []
    for cat in categorias:
        if not isinstance(cat, dict):
            continue
        for c in cat.get("canais") or []:
            if not isinstance(c, dict):
                continue
            nome = texto(c, "nome", "name", "titulo", "title")
            if not nome:
                continue
            saida.append({"nome": nome, "epg": texto(c, "epg")})
    return saida
