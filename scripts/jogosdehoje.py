"""
PASSO 3b — OS JOGOS DE FUTEBOL DO SITE jogosdehojenatv.com.br (hoje e amanha).

O site monta a lista NO NAVEGADOR (a pagina vem vazia e o JavaScript busca
os jogos depois), entao este passo abre o site num Chromium de verdade
(Playwright), espera a lista aparecer e guarda:

    trabalho/jogosdehoje.json
      {"gerado": ts, "metodo": "api" | "dom",
       "jogos": [{"id": "...", "casa": "CRB", "fora": "Náutico",
                  "campeonato": "Brasileirão Série B",
                  "inicio": 1791600000,            <- segundos UTC, horario EXATO
                  "canais": ["Premiere", "SporTV"]}, ...]}

DE ONDE SAEM OS JOGOS (nesta ordem):
  1. as respostas em JSON que o proprio site baixa (tem o horario em UTC,
     os times separados e os canais) — "metodo": "api";
  2. se nao achar JSON, a lista desenhada na tela — "metodo": "dom".

O passo 4 (jogos.py) junta estes jogos com os achados no guia: horario
exato, nomes certos e canais a mais. Se o site falhar, o passo 4 segue so
com o guia (nada quebra).

Rodar sozinho:  pip install playwright && python -m playwright install chromium
                python3 scripts/jogosdehoje.py
"""
import datetime as dt
import json
import os
import re
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "trabalho", "jogosdehoje.json")
URL = "https://www.jogosdehojenatv.com.br/"
BRT = dt.timezone(dt.timedelta(hours=-3))

ESPERA_LISTA_MS = 45000      # quanto espera a lista aparecer
ESPERA_DIA_S = 6             # depois de clicar no dia de amanha

# botao de dia: "Sex 9", "Sáb. 10", "Sat 10"
RX_BOTAO_DIA = re.compile(
    r"^\s*(dom|seg|ter|qua|qui|sex|s[áa]b|sun|mon|tue|wed|thu|fri|sat)\.?\s*(\d{1,2})\s*$", re.I)
RX_SEPARA = re.compile(r"\s+(?:-|x|X|vs\.?|VS\.?|–)\s+")


def eh_futebol(esporte, slug=""):
    t = f"{esporte or ''} {slug or ''}".lower()
    if "americano" in t or "american" in t:
        return False
    return any(p in t for p in ("futebol", "soccer", "football"))


def para_utc(valor):
    """data da API -> segundos UTC (ISO com ou sem fuso, ou numero)"""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        v = int(valor)
        return v // 1000 if v > 10 ** 12 else v
    s = str(valor).strip()
    if not s:
        return None
    if s.isdigit():
        return para_utc(int(s))
    s = s.replace("Z", "+00:00")
    if " " in s and "T" not in s:
        s = s.replace(" ", "T", 1)
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)      # a API manda em UTC
    return int(d.timestamp())


def nome_do_time(v):
    if isinstance(v, dict):
        for k in ("name", "nome", "title", "short_name", "shortName"):
            if isinstance(v.get(k), str) and v[k].strip():
                return v[k].strip()
        return ""
    return str(v or "").strip()


def nomes_dos_canais(lista):
    saida = []
    for c in lista or []:
        if isinstance(c, dict):
            n = c.get("name") or c.get("nome") or c.get("title") or ""
        else:
            n = str(c or "")
        n = n.strip()
        if n and n not in saida:
            saida.append(n)
    return saida


def jogos_do_json(no, achados):
    """procura em qualquer JSON os objetos de jogo (os que tem fixture_id)"""
    if isinstance(no, list):
        for x in no:
            jogos_do_json(x, achados)
        return
    if not isinstance(no, dict):
        return
    if no.get("fixture_id") is not None:
        esporte = no.get("sport") if isinstance(no.get("sport"), str) else nome_do_time(no.get("sport"))
        if eh_futebol(esporte, no.get("sport_slug")):
            casa = nome_do_time(no.get("home_team"))
            fora = nome_do_time(no.get("visiting_team") or no.get("away_team"))
            titulo = str(no.get("title") or "").strip()
            if (not casa or not fora) and titulo:
                partes = RX_SEPARA.split(titulo, maxsplit=1)
                if len(partes) == 2:
                    casa, fora = partes[0].strip(), partes[1].strip()
            ini = para_utc(no.get("date") or no.get("start") or no.get("start_date"))
            if casa and fora and ini:
                liga = no.get("league") if isinstance(no.get("league"), str) else nome_do_time(no.get("league"))
                achados[str(no["fixture_id"])] = {
                    "id": str(no["fixture_id"]), "casa": casa, "fora": fora,
                    "campeonato": (liga or "").strip(), "inicio": ini,
                    "canais": nomes_dos_canais(no.get("channels")),
                }
    for v in no.values():
        if isinstance(v, (dict, list)):
            jogos_do_json(v, achados)


# a lista desenhada na tela (mesmas classes dos sites irmaos, ex.
# livesportsontv.com): esporte > campeonato > jogo
LER_TELA = """
() => {
  const out = [];
  for (const bloco of document.querySelectorAll('[class*="FixtureListBySport_sport__"]')) {
    const esporte = bloco.querySelector('[class*="SectionDivider_label__"]')?.textContent?.trim() || "";
    for (const card of bloco.querySelectorAll('[class*="Card_card__"]')) {
      const liga = card.querySelector('[class*="LeagueCard_cardTitleLink__"]')?.textContent?.trim() || "";
      for (const ev of card.querySelectorAll('[class*="FixtureItem_container__"]')) {
        const link = ev.querySelector('a[href^="/match/"], a[href*="/jogo/"], a[href*="/partida/"]');
        const titulo = (link?.getAttribute("aria-label") || link?.textContent || "").trim();
        const hora = ev.querySelector('[class*="FixtureItem_time__"]')?.textContent?.trim() || "";
        const canais = [...ev.querySelectorAll('[class*="FixtureItem_channelChip__"]')].map(e =>
          (e.querySelector('[class*="FixtureItem_channelChipText__"]')?.textContent?.trim()
           || e.querySelector("img")?.getAttribute("alt")?.trim() || "")).filter(Boolean);
        out.push({esporte, liga, titulo, href: link?.getAttribute("href") || "", hora, canais});
      }
    }
  }
  return out;
}
"""


def jogos_da_tela(itens, dia, achados):
    for it in itens:
        if not eh_futebol(it.get("esporte")):
            continue
        m = re.search(r"(\d{1,2})[:h](\d{2})", it.get("hora") or "")
        partes = RX_SEPARA.split(it.get("titulo") or "", maxsplit=1)
        if not m or len(partes) != 2:
            continue
        ini = int(dt.datetime(dia.year, dia.month, dia.day, int(m.group(1)), int(m.group(2)),
                              tzinfo=BRT).timestamp())
        ident = (re.search(r"(\d+)\D*$", it.get("href") or "") or [None, None])[1] or \
            f"{partes[0]}-{partes[1]}-{ini}"
        achados.setdefault(str(ident), {
            "id": str(ident), "casa": partes[0].strip(), "fora": partes[1].strip(),
            "campeonato": it.get("liga") or "", "inicio": ini,
            "canais": [c for i, c in enumerate(it.get("canais") or []) if c not in (it.get("canais") or [])[:i]],
        })


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright nao instalado — jogosdehojenatv ficou de fora")
        return

    respostas = []
    da_api, da_tela = {}, {}
    hoje = dt.datetime.now(BRT).date()
    amanha = hoje + dt.timedelta(days=1)

    def ler_respostas():
        while respostas:
            r = respostas.pop(0)
            try:
                if "json" not in (r.headers.get("content-type") or ""):
                    continue
                jogos_do_json(r.json(), da_api)
            except Exception:
                pass

    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True)
        ctx = nav.new_context(
            locale="pt-BR", timezone_id="America/Sao_Paulo",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 900},
        )
        pg = ctx.new_page()
        pg.on("response", lambda r: respostas.append(r) if r.status == 200 else None)
        try:
            pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
            try:
                pg.wait_for_selector('[class*="FixtureItem_container__"], a[href^="/match/"]',
                                     timeout=ESPERA_LISTA_MS)
            except Exception:
                print("a lista de jogos nao apareceu no tempo — segue com o que tiver")
            pg.wait_for_timeout(2500)
            ler_respostas()
            # dados que ja vem dentro da pagina (Next.js)
            try:
                bruto = pg.evaluate("() => document.getElementById('__NEXT_DATA__')?.textContent || ''")
                if bruto:
                    jogos_do_json(json.loads(bruto), da_api)
            except Exception:
                pass
            try:
                jogos_da_tela(pg.evaluate(LER_TELA), hoje, da_tela)
            except Exception as e:
                print(f"tela de hoje: {e}")

            # AMANHA: o botao do dia seguinte ("Sáb 10")
            try:
                botoes = pg.locator("button")
                alvo = None
                for i in range(min(botoes.count(), 80)):
                    b = botoes.nth(i)
                    m = RX_BOTAO_DIA.match((b.inner_text(timeout=2000) or "").replace("\n", " "))
                    if m and int(m.group(2)) == amanha.day:
                        alvo = b
                        break
                if alvo is not None:
                    alvo.click(force=True, timeout=10000)
                    time.sleep(ESPERA_DIA_S)
                    ler_respostas()
                    jogos_da_tela(pg.evaluate(LER_TELA), amanha, da_tela)
                else:
                    print("botao de amanha nao achado — so hoje")
            except Exception as e:
                print(f"amanha: {e}")
        finally:
            nav.close()

    metodo, jogos = ("api", da_api) if da_api else ("dom", da_tela)
    # so hoje e amanha (Brasilia)
    de = int(dt.datetime(hoje.year, hoje.month, hoje.day, tzinfo=BRT).timestamp())
    lista = sorted((j for j in jogos.values() if de <= j["inicio"] < de + 2 * 86400),
                   key=lambda j: (j["inicio"], j["casa"]))
    if not lista:
        print("jogosdehojenatv: nenhum jogo lido — o arquivo anterior nao foi trocado")
        return
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump({"gerado": int(time.time()), "metodo": metodo, "jogos": lista},
                  f, ensure_ascii=False, indent=1)
    print(f"jogosdehojenatv: {len(lista)} jogos de futebol ({metodo})")
    for j in lista[:60]:
        print(f"  {dt.datetime.fromtimestamp(j['inicio'], BRT):%d/%m %H:%M}  {j['casa']} x {j['fora']}"
              f"  [{j['campeonato']}]  {', '.join(j['canais'])}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                      # nunca derruba o robo
        print(f"jogosdehojenatv falhou: {e}", file=sys.stderr)
