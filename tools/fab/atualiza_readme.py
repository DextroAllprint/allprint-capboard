#!/usr/bin/env python3
"""Reescreve os blocos gerados do README com os dados do pacote de fabricacao.

So mexe entre os marcadores; o texto escrito a mao fica intacto.
"""

import argparse
import json
import re

INICIO = "<!-- fab:{nome} -->"
FIM = "<!-- /fab:{nome} -->"


def substituir(texto, nome, conteudo):
    inicio, fim = INICIO.format(nome=nome), FIM.format(nome=nome)
    padrao = re.compile(re.escape(inicio) + r".*?" + re.escape(fim), re.DOTALL)
    if not padrao.search(texto):
        raise SystemExit(f"ERRO: marcador '{nome}' nao encontrado no README")
    return padrao.sub(f"{inicio}\n{conteudo}\n{fim}", texto)


def bloco_imagens(meta):
    """Legendas vem de 'legendas' em parametros.json (top/bottom)."""
    leg = meta.get("legendas", {})
    return "\n".join([
        leg.get("top", "Vista de cima (top):"),
        "",
        f"![{leg.get('alt_top', 'Vista de cima da placa')}](docs/img/render_top.png)",
        "",
        leg.get("bottom", "Vista de baixo (bottom):"),
        "",
        f"![{leg.get('alt_bottom', 'Vista de baixo da placa')}](docs/img/render_bottom.png)",
        "",
        "> Renderizadas pelo CI a partir do `.PcbDoc`, a cada alteração do layout.",
    ])


def bloco_dados(meta, base_release):
    projeto = meta["projeto"]

    def link(nome):
        return f"{base_release}/releases/latest/download/{nome}"

    linhas = [
        "Os links abaixo apontam sempre para o **ultimo** pacote publicado — nao",
        "mudam de endereco a cada versao, mesmo com os arquivos versionados por dentro.",
        "",
        "> Como o repositorio e privado, esses links exigem sessao do GitHub no",
        "> navegador. Para baixar por script ou de outro CI, use a API:",
        "> `gh release download --repo <org>/<repo> --pattern '*-latest.*'`.",
        "",
        f"| Baixar | Arquivo |",
        "| --- | --- |",
        f"| **[⬇ Pacote de fabricacao completo]({link(projeto + '-fab-latest.zip')})** | "
        "Gerbers, furacao, BOM, pick and place, previa e esquema |",
        f"| [⬇ BOM de engenharia]({link(projeto + '-bom-latest.csv')}) | "
        "Todos os componentes, com coluna LCSC |",
        f"| [⬇ BOM da JLCPCB]({link(projeto + '-jlcpcb-bom-latest.csv')}) | "
        "Formato de montagem: Comment, Designator, Footprint, LCSC Part # |",
        f"| [⬇ Pick and place da JLCPCB]({link(projeto + '-jlcpcb-cpl-latest.csv')}) | "
        "Designator, Mid X, Mid Y, Layer, Rotation |",
    ]
    if meta.get("tem_esquema"):
        linhas.append(
            f"| [⬇ Esquema eletrico]({link(projeto + '-esquema-latest.pdf')}) | "
            "PDF do esquema |")
    linhas += [
        "",
        f"Versao publicada: **`{meta['versao']}`**. Dentro do pacote os arquivos levam",
        "essa mesma versao no nome. A previa camada a camada esta em",
        "[`docs/PREVIA-GERBERS.md`](docs/PREVIA-GERBERS.md), e o pino a pino de",
        "conectores e CIs em [`docs/PINOUT.md`](docs/PINOUT.md).",
        "",
        "| Item | Valor |",
        "| --- | --- |",
        f"| Dimensoes | {meta['largura_mm']} × {meta['altura_mm']} mm |",
        f"| Camadas de cobre | {meta['camadas_cobre']} |",
        f"| Componentes | {meta['componentes']} |",
        f"| Nets | {meta['nets']} |",
        f"| Trilha minima | {meta['trilha_minima_mm']} mm |",
        f"| Furo minimo | {meta['furo_minimo_mm']} mm |",
    ]
    mont = meta.get("montagem", {})
    if mont:
        linhas += [
            f"| Montagem | {meta.get('casa_montagem', 'JLCPCB')}, SMT lado "
            f"{meta.get('lado_smt', 'bottom')} |",
            f"| Componentes montados | {mont['montados']} de {mont['total']} "
            f"({mont['refs_jlcpcb']} referencia LCSC) |",
            f"| Fornecimento Dextro | {mont['nao_montados']} componentes sem codigo LCSC, "
            "soldados a mao |",
        ]
    linhas += [
        "",
        "Furacao:",
        "",
        "| Diametro | Furos | Tipo |",
        "| --- | --- | --- |",
    ]
    for furo in sorted(meta["furacao"], key=lambda f: (f["tipo"], f["diametro_mm"])):
        linhas.append(f"| {furo['diametro_mm']:.1f} mm | {furo['furos']} | {furo['tipo']} |")
    linhas.append(
        f"| **Total** | **{meta['furos_total']}** | "
        f"{meta['furos_pth']} PTH + {meta['furos_npth']} NPTH |")

    if meta.get("avisos"):
        linhas += ["", "> **Avisos do ultimo build:**", ">"]
        linhas += [f"> - {a}" for a in meta["avisos"]]

    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", default="build/meta.json")
    ap.add_argument("--readme", default="README.md")
    ap.add_argument("--release", default="",
                    help="URL base do repositorio, para montar os links de download")
    args = ap.parse_args()

    with open(args.meta) as fp:
        meta = json.load(fp)
    with open(args.readme) as fp:
        texto = fp.read()

    texto = substituir(texto, "imagens", bloco_imagens(meta))
    texto = substituir(texto, "dados", bloco_dados(meta, args.release))

    with open(args.readme, "w") as fp:
        fp.write(texto)
    print(f"README atualizado ({meta['furos_total']} furos, "
          f"{meta['largura_mm']}x{meta['altura_mm']} mm)")


if __name__ == "__main__":
    main()
