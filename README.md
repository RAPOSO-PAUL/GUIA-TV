# GUIA DE TV (EPG) do CINE GO!

Robô que monta, sozinho, a programação dos canais do app a partir de
**meuguia.tv**, **mi.tv** e **guiadetv.com**, e publica um `guia.json`
pequeno que o app baixa. Roda no GitHub Actions — sem VPS.

## Como funciona

Duas vezes por dia (05:00 e 17:00 de Brasília):

1. **Atualiza as listas de canais** dos três sites (canais novos, nomes novos).
2. **Casa os canais do seu `canais.json`** com os canais dos sites, pelo nome:
   `SPORTV 2 HD3` → chave `sportv2`; `ESPN 1 HD2` → `espn`. As fontes HD1,
   HD2, HD3... do mesmo canal viram uma chave só.
3. **Busca a programação** de hoje e amanhã nos três sites (devagar: 2
   conexões e meio segundo entre pedidos), usando os extratores do
   projeto aberto [iptv-org/epg](https://github.com/iptv-org/epg).
4. **Junta tudo**: para cada canal fica o site que cobre mais das
   próximas 24 h. Se um site falhar, os outros cobrem.
5. Publica o `guia.json` e o `relatorio.md` neste repositório.

Se uma rodada inteira falhar, o `guia.json` anterior continua valendo.

## Instalação (uma vez)

1. Crie um repositório **público** no GitHub (ex.: `GUIA-TV`) e envie
   todos estes arquivos, incluindo a pasta `.github`.
2. **Settings → Actions → General → Workflow permissions** →
   marque **Read and write permissions** → Save.
3. **Actions → Atualizar guia → Run workflow** para a primeira rodada
   (leva uns 5 a 10 minutos).
4. Abra o `relatorio.md` e veja quais canais ficaram com guia.

O endereço que o app vai usar é:

```
https://raw.githubusercontent.com/SEU_USUARIO/GUIA-TV/main/guia.json
```

## Canal sem guia ou com o guia errado

O `relatorio.md` mostra cada canal, de qual site veio e o que ficou
**SEM GUIA**. Para corrigir, use um dos dois:

- **No `canais.json` do app** (mais simples): acrescente no canal
  `"epg": "Nome do canal no site"` — ex.: `"epg": "ESPN Brasil"`.
  O app usa o mesmo campo, então os dois ficam ligados.
- **No `ajustes.json` deste repositório**: force o `site_id` exato em
  cada site (os `site_id` estão nas listas do iptv-org/epg, pasta
  `sites/`). Canais sem programação (ex.: um canal 24 horas de uma série)
  podem ir em `"ignorar"`.

## Formato do `guia.json`

```json
{
  "versao": 1,
  "gerado": 1791136800,
  "canais": {
    "sportv2": {
      "fonte": "meuguia.tv",
      "p": [[inicio, fim, "Título", "Subtítulo", "Categoria", "Descrição"], ...]
    }
  }
}
```

- `inicio` e `fim` em segundos desde 1970 (UTC); o app mostra no fuso do aparelho.
- Os campos do fim podem faltar quando o site não informa.
- Vem das 3 horas passadas até 36 horas à frente.
- A chave do canal segue a mesma regra no robô e no app (ver `scripts/comum.py`).

## Avisos

- Se um site mudar o layout, o extrator dele quebra até o iptv-org/epg
  ser atualizado; os outros dois cobrem nesse meio tempo.
- O GitHub pode pausar tarefas agendadas de repositórios sem atividade
  por 60 dias. Os próprios envios do robô costumam manter o repositório
  ativo, mas se o `guia.json` parar de atualizar, confira em **Actions**.
