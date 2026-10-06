"""
PASSO 3 — junta o que os tres sites devolveram num guia.json pequeno.

Para cada canal escolhe o site que cobre MAIS das proximas 24 h (empate:
a ordem de prioridade do config.json). Grava:

  guia.json       -> o que o app baixa
  relatorio.md    -> o que foi achado, de onde, e o que ficou sem guia
"""
import datetime as dt
import glob
import json
import os
import xml.etree.ElementTree as ET

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRABALHO = os.path.join(RAIZ, "trabalho")


def quando(s):
    """'20261004190000 +0000' -> segundos (UTC)"""
    s = (s or "").strip()
    try:
        return int(dt.datetime.strptime(s, "%Y%m%d%H%M%S %z").timestamp())
    except ValueError:
        try:
            return int(dt.datetime.strptime(s[:14], "%Y%m%d%H%M%S")
                       .replace(tzinfo=dt.timezone.utc).timestamp())
        except ValueError:
            return None


def primeiro_texto(el, tag):
    x = el.find(tag)
    return (x.text or "").strip() if x is not None and x.text else ""


def ler_site(caminho):
    """{chave: [(inicio, fim, titulo, subtitulo, categoria, descricao), ...]}"""
    por_canal = {}
    try:
        raiz = ET.parse(caminho).getroot()
    except ET.ParseError:
        return por_canal
    for p in raiz.iter("programme"):
        ini = quando(p.get("start"))
        if ini is None:
            continue
        fim = quando(p.get("stop"))
        por_canal.setdefault(p.get("channel"), []).append([
            ini, fim,
            primeiro_texto(p, "title"),
            primeiro_texto(p, "sub-title"),
            primeiro_texto(p, "category"),
            primeiro_texto(p, "desc"),
        ])
    for lista in por_canal.values():
        lista.sort(key=lambda x: x[0])
        # sem horario de fim: termina quando o proximo comeca
        for i, item in enumerate(lista):
            if not item[1] or item[1] <= item[0]:
                item[1] = lista[i + 1][0] if i + 1 < len(lista) else item[0] + 3600
    return por_canal


def cobertura(lista, ini, fim):
    """quantos segundos de [ini, fim] a lista cobre"""
    total = 0
    for p in lista:
        a, b = max(p[0], ini), min(p[1], fim)
        if b > a:
            total += b - a
    return total


def main():
    cfg = json.load(open(os.path.join(RAIZ, "config.json"), encoding="utf-8"))
    mapa = json.load(open(os.path.join(TRABALHO, "mapa.json"), encoding="utf-8"))
    agora = int(dt.datetime.now(dt.timezone.utc).timestamp())
    de = agora - cfg.get("horas_para_tras", 3) * 3600
    ate = agora + cfg.get("horas_para_frente", 36) * 3600

    sites = {}
    for site in cfg["prioridade"]:
        arquivos = glob.glob(os.path.join(TRABALHO, f"{site}.xml"))
        sites[site] = ler_site(arquivos[0]) if arquivos else {}

    # se esta rodada falhar inteira, mantem o guia anterior
    total_programas = sum(len(v) for s in sites.values() for v in s.values())
    if total_programas == 0:
        print("NENHUM programa coletado — guia.json anterior mantido")
        raise SystemExit(0)

    canais, linhas_rel = {}, []
    for k in sorted(mapa):
        melhor, melhor_cob = None, -1
        cobs = {}
        escolhida = {}
        for site in cfg["prioridade"]:
            # os candidatos deste site ("chave~1", "chave~2"...): fica o que cobre mais
            lista, c = [], -1
            for cid, progs in sites[site].items():
                if cid.split("~")[0] != k:
                    continue
                cc = cobertura(progs, agora, agora + 24 * 3600)
                if cc > c:
                    lista, c = progs, cc
            cobs[site] = max(c, 0)
            escolhida[site] = lista
            if c > melhor_cob and lista:
                melhor, melhor_cob = site, c
        nomes = ", ".join(sorted(set(mapa[k]["nomes_no_app"]))[:3])
        if not melhor or melhor_cob <= 0:
            achou = ", ".join(mapa[k]["sites"]) or "nenhum site tem este canal"
            linhas_rel.append(f"| `{k}` | {nomes} | — | SEM GUIA ({achou}) |")
            continue
        progs = []
        for p in escolhida[melhor]:
            if p[1] < de or p[0] > ate:
                continue
            progs.append([p[0], p[1], p[2], p[3], p[4], (p[5] or "")[:220]])
        # tira campos vazios do fim (arquivo menor)
        for p in progs:
            while len(p) > 3 and not p[-1]:
                p.pop()
        canais[k] = {"fonte": melhor, "p": progs}
        horas = round(melhor_cob / 3600, 1)
        linhas_rel.append(f"| `{k}` | {nomes} | {melhor} | {len(progs)} programas, {horas} h das próximas 24 h |")

    guia = {"versao": 1, "gerado": agora, "canais": canais}
    with open(os.path.join(RAIZ, "guia.json"), "w", encoding="utf-8") as f:
        json.dump(guia, f, ensure_ascii=False, separators=(",", ":"))

    br = dt.datetime.fromtimestamp(agora, dt.timezone(dt.timedelta(hours=-3)))
    with open(os.path.join(RAIZ, "relatorio.md"), "w", encoding="utf-8") as f:
        f.write(f"# Relatório do guia\n\nGerado em {br:%d/%m/%Y %H:%M} (Brasília). "
                f"{len(canais)} de {len(mapa)} canais com guia.\n\n")
        f.write("| Chave | Nome no app | Fonte | Situação |\n|---|---|---|---|\n")
        f.write("\n".join(linhas_rel) + "\n")
        f.write("\nCanal SEM GUIA: coloque `\"epg\": \"nome do canal no site\"` no canais.json, "
                "ou force o site_id no ajustes.json.\n")
    print(f"guia.json: {len(canais)} canais, {os.path.getsize(os.path.join(RAIZ, 'guia.json'))} bytes")


if __name__ == "__main__":
    main()
