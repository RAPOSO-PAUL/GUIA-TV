"""
PASSO 1 — monta a lista de canais que o iptv-org/epg vai buscar.

Le o canais.json do app, acha cada canal nas listas dos tres sites (pela
CHAVE do nome, ou pelo campo "epg" do canal, ou pelo ajustes.json) e grava:

  trabalho/canais.channels.xml   -> entrada do "npm run grab"
  trabalho/mapa.json             -> o que foi achado (usado no relatorio)
"""
import json
import os
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, os.path.dirname(__file__))
from comum import baixar_json, canais_do_app, chave  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPG = os.path.join(RAIZ, "epg")
TRABALHO = os.path.join(RAIZ, "trabalho")


def main():
    cfg = json.load(open(os.path.join(RAIZ, "config.json"), encoding="utf-8"))
    ajustes = json.load(open(os.path.join(RAIZ, "ajustes.json"), encoding="utf-8"))
    forcar = {k: v for k, v in (ajustes.get("forcar") or {}).items() if not k.startswith("exemplo")}
    ignorar = {chave(x) for x in ajustes.get("ignorar") or []}

    # ---- canais do app: uma chave por canal (HD1..HD4 viram a mesma) ----
    canais = canais_do_app(baixar_json(cfg["canais_url"]))
    chaves = {}
    for c in canais:
        k = chave(c["epg"]) if c.get("epg") else chave(c["nome"])
        if not k or k in ignorar:
            continue
        chaves.setdefault(k, []).append(c["nome"])
    print(f"{len(canais)} canais no app -> {len(chaves)} chaves")

    # ---- listas dos sites (vem com o iptv-org/epg) ----
    por_site = {}
    for site in cfg["prioridade"]:
        # a lista que vem com o iptv-org + a atualizada nesta rodada (somadas)
        caminhos = [os.path.join(EPG, cfg["listas_dos_sites"][site]),
                    os.path.join(TRABALHO, "listas", f"{site}.channels.xml")]
        elementos = []
        for caminho in caminhos:
            try:
                elementos += list(ET.parse(caminho).getroot().iter("channel"))
            except Exception:
                pass                      # lista que nao existe ou veio quebrada
        indice_chave, indice_id = {}, {}
        for el in elementos:
            if not el.get("site_id"):
                continue
            item = {
                "site": el.get("site"), "site_id": el.get("site_id"),
                "lang": el.get("lang") or "pt", "nome": (el.text or "").strip()
            }
            indice_id[item["site_id"]] = item
            # ate 3 candidatos por chave (ex.: "Band" e "Band HD"): o passo 3
            # fica com o que trouxer programacao de verdade
            candidatos = indice_chave.setdefault(chave(item["nome"]), [])
            if len(candidatos) < 3 and all(c["site_id"] != item["site_id"] for c in candidatos):
                candidatos.append(item)
        por_site[site] = (indice_chave, indice_id)
        print(f"  {site}: {len(indice_id)} canais na lista")

    # ---- casar ----
    linhas, mapa = [], {}
    for k, nomes in sorted(chaves.items()):
        achados = {}
        for site in cfg["prioridade"]:
            indice_chave, indice_id = por_site[site]
            sid = (forcar.get(k) or {}).get(site)
            if sid:
                itens = [indice_id[sid]] if sid in indice_id else [
                    {"site": site, "site_id": sid, "lang": "pt", "nome": k}]
            else:
                itens = indice_chave.get(k) or []
            if itens:
                achados[site] = itens
            for n, item in enumerate(itens, 1):
                # "chave~n": o passo 3 junta os candidatos de volta na chave
                linhas.append(
                    f'  <channel site={quoteattr(site)} lang={quoteattr(item["lang"])} '
                    f'xmltv_id={quoteattr(f"{k}~{n}")} site_id={quoteattr(item["site_id"])}>'
                    f'{escape(item["nome"])}</channel>'
                )
        mapa[k] = {
            "nomes_no_app": nomes,
            "sites": {s: [{"site_id": i["site_id"], "nome": i["nome"]} for i in its]
                      for s, its in achados.items()}
        }

    os.makedirs(TRABALHO, exist_ok=True)
    with open(os.path.join(TRABALHO, "canais.channels.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<channels>\n')
        f.write("\n".join(linhas))
        f.write("\n</channels>\n")
    with open(os.path.join(TRABALHO, "mapa.json"), "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=1)

    sem = [k for k, v in mapa.items() if not v["sites"]]
    print(f"{len(linhas)} entradas para buscar; {len(sem)} chave(s) sem nenhum site: {', '.join(sem) or '-'}")


if __name__ == "__main__":
    main()
