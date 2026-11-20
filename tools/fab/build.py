#!/usr/bin/env python3
"""Gera o pacote de fabricacao e montagem da placa.

Fontes:
    .PcbDoc   -> geometria: Gerber, furacao, posicionamento, render 3D
                 (lido pelo importador Altium do KiCad 9, headless, sem Altium)
    .SchDoc   -> BOM: designador, comentario e o codigo LCSC de cada componente
                 (lido direto do binario por tools/fab/esquema.py)
    pinout.py -> PINOUT.md: pino a pino dos conectores e dos CIs principais,
                 tirado das nets do PCB
    pecas.json -> fabricante, encapsulamento e o que vai para a montagem
    parametros.json -> processo de fabricacao

Sai em <out>: fab/ com o pacote, img/ com os renders, <pacote>.zip e meta.json.
"""

import argparse
import csv
import datetime
import glob
import json
import os
import re
import shutil
import string
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import esquema  # noqa: E402
import pinout  # noqa: E402

# Camadas nao-cobre, fixas. O cobre entra depois, conforme a placa.
CAMADAS_FIXAS = [
    ("F.Mask", "gts", "Top Solder Mask"),
    ("B.Mask", "gbs", "Bottom Solder Mask"),
    ("F.Silkscreen", "gto", "Top Silkscreen"),
    ("B.Silkscreen", "gbo", "Bottom Silkscreen"),
    ("F.Paste", "gtp", "Top Paste"),
    ("B.Paste", "gbp", "Bottom Paste"),
    ("Edge.Cuts", "gm1", "Board Outline"),
]

CAMADAS = []


def montar_lista_camadas(n_cobre):
    """Monta a lista de camadas a plotar a partir do numero de camadas de cobre.

    Extensoes Protel: .gtl topo, .gbl fundo, .g1/.g2/... para as internas, que e
    o que o Altium desta casa ja usava.
    """
    cobre = [("F.Cu", "gtl", "Top Copper")]
    for i in range(1, n_cobre - 1):
        cobre.append((f"In{i}.Cu", f"g{i}", f"Inner Copper {i}"))
    cobre.append(("B.Cu", "gbl", "Bottom Copper"))
    CAMADAS[:] = cobre + CAMADAS_FIXAS
    return CAMADAS


avisos = []


def avisar(msg):
    avisos.append(msg)
    print(f"::warning::{msg}" if os.environ.get("GITHUB_ACTIONS") else f"AVISO: {msg}")


def mm(valor):
    return pcbnew.ToMM(valor)


# ----------------------------------------------------------------- geometria

def importar(pcbdoc, dir_kicad):
    """Le o .PcbDoc, normaliza a origem no canto inferior esquerdo e salva."""
    board = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.ALTIUM_DESIGNER, pcbdoc)

    # Gerber, furacao e CPL precisam compartilhar a mesma origem. Ancorar no
    # canto da placa deixa tudo positivo, que e o que a casa de montagem espera.
    caixa = board.GetBoardEdgesBoundingBox()
    origem = pcbnew.VECTOR2I(caixa.GetLeft(), caixa.GetBottom())
    board.GetDesignSettings().SetAuxOrigin(origem)

    os.makedirs(dir_kicad, exist_ok=True)
    projeto = os.path.join(dir_kicad, "placa.kicad_pro")
    destino = os.path.join(dir_kicad, "placa.kicad_pcb")
    gestor = pcbnew.GetSettingsManager()
    gestor.LoadProject(projeto, False)
    try:
        board.SetProject(gestor.GetProject(projeto))
    except Exception:
        pass
    pcbnew.SaveBoard(destino, board)
    return board, destino, origem


def plotar_gerbers(kicad_pcb, dir_gerber, projeto):
    """Plota as camadas pelo kicad-cli.

    Nao usar PLOT_CONTROLLER aqui: pela API ele contamina o Edge.Cuts com
    geometria que nao pertence ao contorno (443 coordenadas em vez de 8), e o
    fabricante recortaria a placa errada. O kicad-cli sai limpo.
    """
    os.makedirs(dir_gerber, exist_ok=True)
    camadas = ",".join(nome for nome, _ext, _desc in CAMADAS)
    subprocess.run(
        ["kicad-cli", "pcb", "export", "gerbers", "--no-x2", "--use-drill-file-origin",
         "--subtract-soldermask", "--layers", camadas, "-o", dir_gerber, kicad_pcb],
        check=True, stdout=subprocess.DEVNULL,
    )
    # o kicad-cli nomeia pelo rotulo da camada vindo do Altium ("Top Layer"),
    # com espaco no meio; renomeia para <projeto>-<camada>.<ext>
    for arquivo in os.listdir(dir_gerber):
        caminho = os.path.join(dir_gerber, arquivo)
        ext = arquivo.rsplit(".", 1)[-1].lower()
        if ext == "gbrjob":
            os.remove(caminho)
            continue
        alvo = next((n for n, e, _d in CAMADAS if e == ext), None)
        if alvo:
            os.rename(caminho, os.path.join(dir_gerber, f"{projeto}-{alvo}.{ext}"))


def furar(kicad_pcb, dir_drill, projeto):
    """Furacao Excellon, na mesma origem dos Gerbers (--drill-origin plot)."""
    os.makedirs(dir_drill, exist_ok=True)
    subprocess.run(
        ["kicad-cli", "pcb", "export", "drill", "--format", "excellon",
         "--drill-origin", "plot", "--excellon-zeros-format", "decimal",
         "--excellon-separate-th", "--generate-map", "--map-format", "pdf",
         "-o", dir_drill + os.sep, kicad_pcb],
        check=True, stdout=subprocess.DEVNULL,
    )
    for arquivo in os.listdir(dir_drill):
        if arquivo.startswith("placa"):
            os.rename(os.path.join(dir_drill, arquivo),
                      os.path.join(dir_drill, projeto + arquivo[len("placa"):]))


def ler_furacao(dir_drill):
    tabela = []
    for arquivo in sorted(os.listdir(dir_drill)):
        if not arquivo.lower().endswith(".drl"):
            continue
        tipo = "NPTH" if "NPTH" in arquivo.upper() else "PTH"
        diametros, atual, contagem = {}, None, Counter()
        with open(os.path.join(dir_drill, arquivo)) as fp:
            for linha in fp:
                linha = linha.strip()
                if linha.startswith("T") and "C" in linha:
                    ferramenta, _, diam = linha.partition("C")
                    try:
                        diametros[ferramenta] = float(diam)
                    except ValueError:
                        pass
                elif linha.startswith("T") and linha[1:].isdigit():
                    atual = linha
                elif linha.startswith("X") and atual:
                    contagem[atual] += 1
        for ferramenta, furos in sorted(contagem.items(), key=lambda kv: diametros.get(kv[0], 0)):
            tabela.append((diametros.get(ferramenta, 0.0), furos, tipo))
    return tabela


def furacao_do_drr(caminho):
    """Furacao segundo o relatorio do Altium.

    Devolve (contagem por diametro e tipo, quantos o Altium marca como nao
    redondos). Os nao redondos entram na contagem porque e assim que este
    pacote os emite — redondos, no diametro nominal — mas sao contados a parte
    para virar aviso, ja que a forma deixa de ser a do projeto original.
    """
    contagem, nao_redondos = Counter(), 0
    with open(caminho, errors="ignore") as fp:
        for linha in fp:
            campos = linha.split()
            if len(campos) < 4 or not campos[0].startswith("T") or "mm" not in campos[1]:
                continue
            try:
                diam = round(float(campos[1].replace("mm", "")), 3)
            except ValueError:
                continue
            numeros = [c for c in campos if c.isdigit()]
            if not numeros:
                continue
            if "Round" not in linha:
                nao_redondos += int(numeros[-1])
            contagem[(diam, "NPTH" if "NPTH" in linha else "PTH")] += int(numeros[-1])
    return contagem, nao_redondos


# ----------------------------------------------------------------- montagem

def encapsulamento_do_footprint(nome):
    """RES-0603 -> '0603'. Devolve None quando nao da pra inferir."""
    for tamanho in ("01005", "0201", "0402", "0603", "0805", "1206", "1210", "2010", "2512"):
        if tamanho in nome:
            return tamanho
    return None


def montar_bom(board, folhas, pecas, params):
    """Junta o esquema (BOM, LCSC) com o PCB (footprint, lado, posicao).

    O esquema desta placa e multifolha, entao le todas e junta. Designador
    repetido entre folhas seria erro de projeto, e o build reclama.
    """
    do_esquema, origem_folha, multiparte = {}, {}, Counter()
    for folha in folhas:
        for comp in esquema.componentes(folha):
            ref = comp["designador"]
            if ref in do_esquema:
                if origem_folha[ref] == folha:
                    # Simbolo multiparte: o mesmo componente fisico desenhado em
                    # varias partes na mesma folha. Uma peca so na BOM.
                    multiparte[ref] += 1
                else:
                    avisar(f"designador {ref} aparece em duas folhas: "
                           f"{os.path.basename(origem_folha[ref])} e "
                           f"{os.path.basename(folha)}")
                continue
            do_esquema[ref] = comp
            origem_folha[ref] = folha
    if multiparte:
        refs = sorted(multiparte)
        print(f"   {len(refs)} simbolos multiparte agrupados: {', '.join(refs[:8])}"
              + (" ..." if len(refs) > 8 else ""))

    do_pcb, sem_designador = {}, 0
    for fp in board.GetFootprints():
        if not fp.GetReference().strip():
            # logotipo, furo de fixacao, marca de painel: nao e peca
            sem_designador += 1
            continue
        pads = list(fp.Pads())
        tht = any(pd.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
                  for pd in pads)
        do_pcb[fp.GetReference()] = {
            "footprint": fp.GetFPIDAsString().split(":")[-1],
            "tecnologia": "THT" if tht else "SMD",
            "lado": "bottom" if fp.IsFlipped() else "top",
            "valor": fp.GetValue(),
        }

    # Projeto multicanal: quando uma folha e instanciada mais de uma vez, o
    # Altium sufixa o designador no PCB (C22 no esquema vira C22A e C22B).
    # Sem desfazer isso, esses componentes sumiriam da BOM e da montagem.
    canais = {}
    for ref in do_pcb:
        if ref in do_esquema:
            continue
        base = ref.rstrip(string.ascii_uppercase)
        if base and base != ref and base in do_esquema:
            canais[ref] = base
    if canais:
        bases = sorted(set(canais.values()))
        avisar(f"projeto multicanal: {len(canais)} componentes do PCB vem de "
               f"{len(bases)} simbolos instanciados mais de uma vez "
               f"({bases[0]}..{bases[-1]}); a BOM os expande")

    if sem_designador:
        print(f"   {sem_designador} footprints do PCB sem designador, ignorados "
              "(logotipo, furo de fixacao e afins)")

    so_no_esquema = sorted(set(do_esquema) - {canais.get(r, r) for r in do_pcb})
    so_no_pcb = sorted(set(do_pcb) - set(do_esquema) - set(canais))
    if so_no_esquema:
        avisar(f"componentes no esquema e ausentes do PCB: {', '.join(so_no_esquema)}")
    if so_no_pcb:
        avisar(f"componentes no PCB e ausentes do esquema: {', '.join(so_no_pcb)}")

    substituidos = defaultdict(list)
    montaveis = [r for r in do_pcb if r in do_esquema or r in canais]
    linhas = []
    for designador in sorted(montaveis,
                             key=lambda d: (d[0], int("".join(filter(str.isdigit, d)) or 0), d)):
        sch = do_esquema[canais.get(designador, designador)]
        pcb = do_pcb[designador]
        lcsc = sch["lcsc"].strip()
        lcsc, peca = resolver_peca(lcsc, pecas, designador, substituidos)
        linhas.append({
            "designador": designador,
            "comentario": sch["comentario"],
            "footprint": pcb["footprint"],
            "tecnologia": pcb["tecnologia"],
            "lado": pcb["lado"],
            "descricao": peca.get("descricao") or sch["descricao"],
            "lcsc": lcsc,
            "fabricante": peca.get("fabricante", ""),
            "codigo_fabricante": peca.get("codigo", ""),
            # padrao: tem codigo LCSC, vai para a montagem. pecas.json e excecao.
            "montar_jlcpcb": bool(lcsc) and peca.get("montar_jlcpcb", True),
        })

    # Exclusao por designador: opcao de montagem (par de 0R mutuamente
    # exclusivo, jumper de configuracao) que o esquema nao marca como DNP.
    nao_montar = params["montagem"].get("nao_montar", {})
    desconhecidos = sorted(set(nao_montar) - {l["designador"] for l in linhas})
    if desconhecidos:
        avisar(f"montagem.nao_montar cita designadores que nao estao na placa: "
               f"{', '.join(desconhecidos)}")
    for linha in linhas:
        if linha["designador"] in nao_montar and linha["montar_jlcpcb"]:
            linha["montar_jlcpcb"] = False
            avisar(f"{linha['designador']} fora da montagem por parametros.json: "
                   f"{nao_montar[linha['designador']]}")

    for (de, para), designadores in substituidos.items():
        avisar(f"peca substituida: o esquema pede {de} mas a BOM sai com {para} em "
               f"{len(designadores)} componentes ({designadores[0]}..{designadores[-1]}) — "
               f"{pecas[de].get('motivo', 'ver tools/fab/pecas.json')}")

    conferir_encapsulamento(linhas, pecas, params)
    conferir_pares_0r(board, linhas, params)
    return linhas


ZERO_OHM = re.compile(r"^(0|0R|0R0|0E|0 ?OHMS?|0\.0)$", re.IGNORECASE)


def conferir_pares_0r(board, linhas, params):
    """Barra dois 0R montados que levam um no de opcao a duas nets diferentes.

    E o desenho classico de opcao de montagem (R9 leva o pino a 3,3V, R10 a
    VSYS): monta-se UM. Montar os dois curto-circuita as duas alimentacoes. O
    esquema raramente marca isso, entao a checagem e feita no cobre.

    So vale quando a net em comum e o NO DE OPCAO, ou seja, menor (em pads) que
    as duas pontas. Quando a net em comum e o trilho (5V distribuido por dois
    0R para duas cargas), nao ha curto, e o par nao e acusado.
    """
    montados = {l["designador"] for l in linhas if l["montar_jlcpcb"]}
    aceitos = {frozenset(p) for p in params["montagem"].get("pares_0r_aceitos", [])}
    tamanho = Counter(pd.GetNetname() for fp in board.GetFootprints()
                      for pd in fp.Pads() if pd.GetNetname())
    por_net = defaultdict(list)
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref not in montados or not ZERO_OHM.match(fp.GetValue().strip()):
            continue
        nets = [pd.GetNetname() for pd in fp.Pads() if pd.GetNetname()]
        if len(set(nets)) != 2:
            continue
        for i, net in enumerate(nets[:2]):
            por_net[net].append((ref, nets[1 - i]))
    erros = set()
    for net, ligados in por_net.items():
        for i, (ra, outra_a) in enumerate(ligados):
            for rb, outra_b in ligados[i + 1:]:
                no_de_opcao = tamanho[net] < min(tamanho[outra_a], tamanho[outra_b])
                if (outra_a != outra_b and no_de_opcao
                        and frozenset((ra, rb)) not in aceitos):
                    erros.add((tuple(sorted((ra, rb))), net.lstrip("/"),
                               tuple(sorted((outra_a.lstrip("/"), outra_b.lstrip("/"))))))
    for (ra, rb), net, (na, nb) in sorted(erros):
        print(f"ERRO: {ra} e {rb} (0R) estao os dois na montagem e ligam {net} a "
              f"{na} e a {nb} — curto entre {na} e {nb}. Monte so um: ponha o outro em "
              "montagem.nao_montar (ou, se for intencional, o par em "
              "montagem.pares_0r_aceitos) em tools/fab/parametros.json.", file=sys.stderr)
    if erros:
        raise SystemExit(1)


def resolver_peca(lcsc, pecas, designador, substituidos):
    """Aplica 'substituir_por' quando o esquema esta defasado do PCB."""
    if not lcsc:
        return "", {}
    peca = pecas.get(lcsc, {})
    troca = peca.get("substituir_por")
    if troca and troca in pecas:
        substituidos[(lcsc, troca)].append(designador)
        return troca, pecas[troca]
    return lcsc, peca


def previa_camadas(kicad_pcb, dir_previa, projeto, versao):
    """Uma imagem por camada, sempre com o contorno da placa por baixo.

    --common-layers poe o Edge.Cuts em toda pagina, entao cada camada aparece
    registrada contra o mesmo contorno e da pra comparar uma com a outra.
    """
    os.makedirs(dir_previa, exist_ok=True)
    pdfs = os.path.join(dir_previa, "pdf")
    os.makedirs(pdfs, exist_ok=True)

    gerados = []
    for nome, ext, descricao in CAMADAS:
        rotulo = nome.replace(".", "_")
        # --mode-single da o nome exato do arquivo; incluir Edge.Cuts na lista
        # mantem o contorno visivel em toda camada.
        camadas = nome if nome == "Edge.Cuts" else f"{nome},Edge.Cuts"
        pdf = os.path.join(pdfs, f"{rotulo}.pdf")
        subprocess.run(
            ["kicad-cli", "pcb", "export", "pdf", "--mode-single", "--black-and-white",
             "--layers", camadas, "-o", pdf, kicad_pcb],
            check=True, stdout=subprocess.DEVNULL,
        )
        if not os.path.exists(pdf):
            avisar(f"previa: nao saiu PDF para a camada {nome}")
            continue
        base = os.path.join(dir_previa, rotulo)
        subprocess.run(["pdftoppm", "-r", "150", "-png", "-singlefile", pdf, base],
                       check=True)
        gerados.append((nome, ext, descricao, rotulo + ".png"))

    shutil.rmtree(pdfs)

    linhas = [
        f"# Previa dos Gerbers — {projeto}",
        "",
        f"Versao do pacote: **{versao}**.",
        "",
        "Uma imagem por camada, renderizada do mesmo `.kicad_pcb` que gerou os",
        "Gerbers. O contorno da placa (`Edge.Cuts`, o Mechanical 1 do Altium) esta",
        "presente em **todas** elas, fixo, para servir de registro: qualquer camada",
        "deslocada salta aos olhos na comparacao.",
        "",
        "Conferir antes de mandar fabricar: contorno fechado, ausencia de cobre",
        "invadindo a borda, silk fora de pad, e furacao dentro do contorno.",
        "",
    ]
    for nome, ext, descricao, arquivo in gerados:
        linhas += [
            f"## {descricao} (`.{ext}`)",
            "",
            f"Camada `{nome}` sobre o contorno da placa.",
            "",
            f"![{descricao}]({arquivo})",
            "",
        ]
    open(os.path.join(dir_previa, "PREVIA-GERBERS.md"), "w").write("\n".join(linhas))
    return [a for _n, _e, _d, a in gerados]


def conferir_furos_no_contorno(dir_drill, medidas):
    """Avisa sobre furo caindo fora do contorno: a casa vai abrir consulta."""
    fora = []
    for arquivo in sorted(os.listdir(dir_drill)):
        if not arquivo.lower().endswith(".drl"):
            continue
        for linha in open(arquivo and os.path.join(dir_drill, arquivo)):
            achado = re.match(r"^X(-?[\d.]+)Y(-?[\d.]+)", linha.strip())
            if not achado:
                continue
            x, y = float(achado.group(1)), float(achado.group(2))
            if not (0 <= x <= medidas["largura_mm"] and 0 <= y <= medidas["altura_mm"]):
                fora.append((arquivo, x, y))
    if fora:
        arquivos = sorted({a for a, _x, _y in fora})
        avisar(f"{len(fora)} furos caem fora do contorno da placa ({', '.join(arquivos)}); "
               "em geral e furo de fixacao de conector que o footprint do Altium modela "
               "alem da borda — confirmar com a casa antes de fabricar")
    return len(fora)


def conferir_encapsulamento(linhas, pecas, params):
    """Barra peca comprada num encapsulamento que nao e o do land pattern."""
    divergencias = []
    for linha in linhas:
        if not linha["lcsc"]:
            continue
        esperado = pecas.get(linha["lcsc"], {}).get("encapsulamento")
        obtido = encapsulamento_do_footprint(linha["footprint"])
        if esperado and obtido and esperado != obtido:
            divergencias.append((linha["designador"], linha["lcsc"], esperado, obtido))

    if not divergencias:
        return

    porgrupo = defaultdict(list)
    for designador, lcsc, esperado, obtido in divergencias:
        porgrupo[(lcsc, esperado, obtido)].append(designador)

    for (lcsc, esperado, obtido), designadores in porgrupo.items():
        msg = (f"encapsulamento divergente: {lcsc} e {esperado} no esquema, mas o land "
               f"pattern do PCB e {obtido} em {len(designadores)} componentes "
               f"({designadores[0]}..{designadores[-1]})")
        if params["montagem"].get("aceitar_divergencia_encapsulamento"):
            avisar(msg + " — aceito por parametros.json")
        else:
            print(f"ERRO: {msg}", file=sys.stderr)

    if not params["montagem"].get("aceitar_divergencia_encapsulamento"):
        print("ERRO: corrija o footprint no PCB ou o codigo LCSC no esquema. Para "
              "liberar mesmo assim, ligue aceitar_divergencia_encapsulamento em "
              "tools/fab/parametros.json.", file=sys.stderr)
        raise SystemExit(1)


def escrever_bom(caminho, linhas):
    """BOM de engenharia: todos os componentes, agrupados por peca."""
    grupos = defaultdict(list)
    for linha in linhas:
        chave = (linha["comentario"], linha["footprint"], linha["lcsc"],
                 linha["tecnologia"], linha["lado"], linha["fabricante"],
                 linha["codigo_fabricante"], linha["descricao"])
        grupos[chave].append(linha["designador"])

    with open(caminho, "w", newline="") as fp:
        escritor = csv.writer(fp)
        escritor.writerow(["Item", "Quantidade", "Designadores", "Comentario",
                           "Footprint", "Tecnologia", "Lado", "LCSC", "Fabricante",
                           "Codigo do fabricante", "Descricao", "Montar na JLCPCB"])
        for item, (chave, designadores) in enumerate(sorted(grupos.items()), 1):
            comentario, footprint, lcsc, tecnologia, lado, fab, codigo, descricao = chave
            monta = any(l["montar_jlcpcb"] for l in linhas if l["designador"] in designadores)
            escritor.writerow([item, len(designadores), ",".join(designadores),
                               comentario, footprint, tecnologia, lado, lcsc, fab,
                               codigo, descricao, "sim" if monta else "nao"])
    return len(grupos)


def escrever_bom_jlcpcb(caminho, linhas):
    """BOM no formato da JLCPCB: Comment, Designator, Footprint, LCSC Part #."""
    grupos = defaultdict(list)
    for linha in linhas:
        if linha["montar_jlcpcb"]:
            grupos[(linha["comentario"], linha["footprint"], linha["lcsc"])].append(
                linha["designador"])

    with open(caminho, "w", newline="") as fp:
        escritor = csv.writer(fp)
        escritor.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (comentario, footprint, lcsc), designadores in sorted(grupos.items()):
            escritor.writerow([comentario, ",".join(designadores), footprint, lcsc])
    return sum(len(d) for d in grupos.values())


def escrever_cpl_jlcpcb(caminho, kicad_pcb, linhas, dir_trabalho):
    """CPL no formato da JLCPCB, a partir do pos file do kicad-cli.

    O pos sai com --use-drill-file-origin, a mesma origem dos Gerbers e da
    furacao, entao as coordenadas ja chegam alinhadas na casa de montagem.
    """
    bruto = os.path.join(dir_trabalho, "pos.csv")
    subprocess.run(
        ["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm",
         "--side", "both", "--use-drill-file-origin", "-o", bruto, kicad_pcb],
        check=True, stdout=subprocess.DEVNULL,
    )

    montar = {l["designador"] for l in linhas if l["montar_jlcpcb"]}
    escritos = 0
    with open(bruto, newline="") as entrada, open(caminho, "w", newline="") as saida:
        leitor = csv.DictReader(entrada)
        escritor = csv.writer(saida)
        escritor.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for reg in leitor:
            if reg["Ref"] not in montar:
                continue
            escritor.writerow([reg["Ref"], f'{float(reg["PosX"]):.4f}',
                               f'{float(reg["PosY"]):.4f}', reg["Side"].capitalize(),
                               f'{float(reg["Rot"]):.2f}'])
            escritos += 1
    return escritos


# ------------------------------------------------------------------ esquema

def commit_do_arquivo(caminho):
    try:
        saida = subprocess.run(["git", "log", "-1", "--format=%ct", "--", caminho],
                               capture_output=True, text=True, check=True).stdout.strip()
        return int(saida) if saida else None
    except Exception:
        return None


def copiar_esquema(params, destino):
    """Poe o PDF do esquema no pacote e avisa se ele estiver defasado.

    O PDF nao e regenerado aqui: o importador de .SchDoc do KiCad so existe na
    GUI, entao ele continua saindo do OutJob do Altium, a mao.
    """
    origem = params["esquema_pdf"]
    if not os.path.exists(origem):
        avisar(f"PDF do esquema nao encontrado em {origem}; pacote sai sem o esquema")
        return False

    t_pdf = commit_do_arquivo(origem)
    folhas = sorted(glob.glob(params.get("esquema_glob", "*.SchDoc")))
    mudadas = [f for f in folhas
               if (commit_do_arquivo(f) or 0) > (t_pdf or 0)] if t_pdf else []
    if mudadas:
        avisar(f"{len(mudadas)} folha(s) de esquema mudaram depois de {origem} "
               f"({', '.join(os.path.basename(f) for f in mudadas[:3])}"
               f"{' ...' if len(mudadas) > 3 else ''}): reexporte o PDF do esquema "
               "pelo OutJob do Altium e commite junto")

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    shutil.copy2(origem, destino)
    return True


# ------------------------------------------------------------------ relatos

def medir(board, dir_drill):
    caixa = board.GetBoardEdgesBoundingBox()
    larguras = [t.GetWidth() for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    furacao = ler_furacao(dir_drill)
    return {
        "largura_mm": round(mm(caixa.GetWidth()), 2),
        "altura_mm": round(mm(caixa.GetHeight()), 2),
        "camadas_cobre": board.GetCopperLayerCount(),
        "componentes": len(board.GetFootprints()),
        "trilhas": len(board.GetTracks()),
        "nets": board.GetNetCount(),
        "trilha_minima_mm": round(mm(min(larguras)), 3) if larguras else None,
        "furo_minimo_mm": min((d for d, _, _ in furacao), default=None),
        "furos_total": sum(n for _, n, _ in furacao),
        "furos_pth": sum(n for _, n, t in furacao if t == "PTH"),
        "furos_npth": sum(n for _, n, t in furacao if t == "NPTH"),
        "furacao": [{"diametro_mm": d, "furos": n, "tipo": t} for d, n, t in furacao],
    }


def validar(dir_gerber, medidas, drr):
    erros = []
    presentes = {a.rsplit(".", 1)[-1].lower() for a in os.listdir(dir_gerber)}
    for _nome, ext, descricao in CAMADAS:
        if ext not in presentes:
            erros.append(f"camada ausente: .{ext} ({descricao})")
    for arquivo in os.listdir(dir_gerber):
        if os.path.getsize(os.path.join(dir_gerber, arquivo)) == 0:
            erros.append(f"arquivo vazio: {arquivo}")
    if medidas["furos_total"] == 0:
        erros.append("nenhum furo na furacao")

    if drr and os.path.exists(drr):
        esperado, nao_redondos = furacao_do_drr(drr)
        if nao_redondos:
            avisar(f"o Altium marca {nao_redondos} furos como quadrados ou retangulares, "
                   "e este pacote os emite como REDONDOS do mesmo diametro nominal "
                   "(o .drl nao tem nenhuma rota G85). O total de furos bate, a forma "
                   "nao — decidir com a casa se atende")
        obtido = Counter()
        for furo in medidas["furacao"]:
            obtido[(round(furo["diametro_mm"], 3), furo["tipo"])] += furo["furos"]
        if esperado and esperado != obtido:
            erros.append(f"furacao divergente do relatorio do Altium: "
                         f"so no Altium {dict(esperado - obtido)}, "
                         f"so no KiCad {dict(obtido - esperado)}")

    if erros:
        for erro in erros:
            print(f"ERRO: {erro}", file=sys.stderr)
        raise SystemExit(1)


def escrever_instrucoes(caminho, params, medidas, montagem, versao, nomes):
    proc, mont = params["processo"], params["montagem"]
    linhas = [
        f"# Instrucoes de fabricacao e montagem — {params['projeto']}",
        "",
        f"Desenho Dextro **{params['numero_dextro']}**, revisao **{params['revisao']}**.",
        f"Versao do pacote: **{versao}**. Gerado automaticamente dos arquivos de projeto.",
        "",
        "## Fabricacao da placa",
        "",
        "| Item | Valor |",
        "| --- | --- |",
        f"| Dimensoes | {medidas['largura_mm']} x {medidas['altura_mm']} mm |",
        f"| Camadas de cobre | {medidas['camadas_cobre']} |",
        f"| Material | {proc['material']} |",
        f"| Espessura | {proc['espessura_mm']} mm |",
        f"| Cobre externo | {proc['cobre_externo_oz']} oz |",
        f"| Mascara de solda | {proc['mascara_cor']} |",
        f"| Silkscreen | {proc['silk_cor']} |",
        f"| Acabamento | {proc['acabamento']} |",
        f"| Tolerancia de contorno | +/- {proc['tolerancia_contorno_mm']} mm |",
        f"| Teste eletrico | {proc['teste_eletrico']} |",
        f"| Quantidade | {proc['quantidade_prototipo']} |",
        f"| Trilha minima | {medidas['trilha_minima_mm']} mm |",
        f"| Furo minimo | {medidas['furo_minimo_mm']} mm |",
        "",
        "Origem dos Gerber, da furacao e do CPL: canto inferior esquerdo da placa,",
        "todas as coordenadas positivas e no mesmo referencial.",
        "",
        "## Montagem",
        "",
        f"Casa de montagem: **{mont['casa']}**. Apenas SMT, lado **{mont['lado_smt']}**.",
        "",
        f"- Componentes montados: **{montagem['montados']}** de {montagem['total']}",
        f"- Referencias distintas na montagem: {montagem['refs_jlcpcb']}",
        f"- Fornecimento Dextro (soldados a mao, fora do CPL): {montagem['nao_montados']} "
        "componentes sem codigo LCSC",
        "",
        "Componente sem codigo LCSC no esquema nao vai para a montagem: e peca Dextro,",
        "soldada a mao (em geral os conectores THT).",
        "",
        "## Arquivos",
        "",
        "| Arquivo | Conteudo |",
        "| --- | --- |",
    ]
    for _nome, ext, descricao in CAMADAS:
        linhas.append(f"| `Gerber/*.{ext}` | {descricao} |")
    linhas += [
        "| `NCDrill/*-PTH.drl` | Furacao metalizada (Excellon, metrico) |",
        "| `NCDrill/*-NPTH.drl` | Furacao nao metalizada (Excellon, metrico) |",
        f"| `Montagem/{nomes['bom']}` | BOM de engenharia, todos os componentes |",
        f"| `Montagem/{nomes['bom_jlcpcb']}` | BOM no formato JLCPCB |",
        f"| `Montagem/{nomes['cpl']}` | Pick and place no formato JLCPCB |",
        f"| `Esquema/{nomes['esquema']}` | Esquema eletrico |",
        "",
        "Gerber RS-274X, aberturas embutidas, unidade metrica, extensoes Protel.",
        "",
        "## Furacao",
        "",
        "| Diametro | Furos | Tipo |",
        "| --- | --- | --- |",
    ]
    for furo in medidas["furacao"]:
        linhas.append(f"| {furo['diametro_mm']:.1f} mm | {furo['furos']} | {furo['tipo']} |")
    linhas += [
        f"| **Total** | **{medidas['furos_total']}** | "
        f"{medidas['furos_pth']} PTH + {medidas['furos_npth']} NPTH |",
        "",
        "## Observacoes",
        "",
    ]
    linhas += [f"- {obs}" for obs in params["observacoes"]]
    if avisos:
        linhas += ["", "## Avisos do build", ""] + [f"- {a}" for a in avisos]
    linhas.append("")
    open(caminho, "w").write("\n".join(linhas))


def renderizar(kicad_pcb, dir_img):
    os.makedirs(dir_img, exist_ok=True)
    for lado in ("top", "bottom"):
        subprocess.run(
            ["kicad-cli", "pcb", "render", "-o", os.path.join(dir_img, f"render_{lado}.png"),
             "--side", lado, "--quality", "high", "--width", "2000", "--height", "1500",
             "--background", "transparent", kicad_pcb],
            check=True, stdout=subprocess.DEVNULL,
        )


def zipar(dir_fab, destino):
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for raiz, _dirs, arquivos in os.walk(dir_fab):
            for arquivo in sorted(arquivos):
                caminho = os.path.join(raiz, arquivo)
                zf.write(caminho, os.path.relpath(caminho, dir_fab))


# --------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcb", default=None, help="padrao: 'pcb' de parametros.json")
    ap.add_argument("--params", default="tools/fab/parametros.json")
    ap.add_argument("--pecas", default="tools/fab/pecas.json")
    ap.add_argument("--drr", default=None, help="padrao: 'drr' de parametros.json")
    ap.add_argument("--out", default="build")
    ap.add_argument("--commit", default=os.environ.get("GITHUB_SHA", "local")[:7])
    ap.add_argument("--sem-render", action="store_true")
    args = ap.parse_args()

    params = json.load(open(args.params))
    args.pcb = args.pcb or params["pcb"]
    args.drr = args.drr or params.get("drr")
    pecas = {k: v for k, v in json.load(open(args.pecas)).items() if not k.startswith("_")}

    data = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    versao = f"rev{params['revisao']}-{data}-{args.commit}"
    projeto = params["projeto"]
    nomes = {
        "zip": f"{projeto}-fab-{versao}.zip",
        "bom": f"{projeto}-bom-{versao}.csv",
        "bom_jlcpcb": f"{projeto}-jlcpcb-bom-{versao}.csv",
        "cpl": f"{projeto}-jlcpcb-cpl-{versao}.csv",
        "esquema": f"{projeto}-esquema-{versao}.pdf",
    }

    if os.path.isdir(args.out):
        shutil.rmtree(args.out)
    dir_fab = os.path.join(args.out, "fab")
    dir_gerber, dir_drill = os.path.join(dir_fab, "Gerber"), os.path.join(dir_fab, "NCDrill")
    dir_mont, dir_esq = os.path.join(dir_fab, "Montagem"), os.path.join(dir_fab, "Esquema")
    os.makedirs(dir_mont, exist_ok=True)

    print(f"-> importando {args.pcb}")
    board, kicad_pcb, _origem = importar(args.pcb, os.path.join(args.out, "kicad"))
    montar_lista_camadas(board.GetCopperLayerCount())
    print(f"   {board.GetCopperLayerCount()} camadas de cobre -> "
          f"{len(CAMADAS)} camadas a plotar")

    print("-> plotando Gerbers")
    plotar_gerbers(kicad_pcb, dir_gerber, projeto)
    print("-> gerando furacao")
    furar(kicad_pcb, dir_drill, projeto)

    medidas = medir(board, dir_drill)
    print(f"   {medidas['largura_mm']} x {medidas['altura_mm']} mm, "
          f"{medidas['camadas_cobre']} camadas, {medidas['furos_total']} furos")

    print("-> validando a geometria")
    validar(dir_gerber, medidas, args.drr)
    furos_fora = conferir_furos_no_contorno(dir_drill, medidas)

    if glob.glob("*.PrjPcbVariants") and not params["montagem"].get("nao_montar"):
        avisar("o projeto tem variantes do Altium (.PrjPcbVariants), que este build "
               "nao le: o que a variante deixa de fora precisa estar em "
               "montagem.nao_montar")

    folhas = sorted(glob.glob(params.get("esquema_glob", "*.SchDoc")))
    if not folhas:
        raise SystemExit("ERRO: nenhuma folha de esquema encontrada")
    print(f"-> montando a BOM a partir de {len(folhas)} folhas de esquema")
    linhas = montar_bom(board, folhas, pecas, params)
    refs = escrever_bom(os.path.join(dir_mont, nomes["bom"]), linhas)
    montados = escrever_bom_jlcpcb(os.path.join(dir_mont, nomes["bom_jlcpcb"]), linhas)
    posicoes = escrever_cpl_jlcpcb(os.path.join(dir_mont, nomes["cpl"]), kicad_pcb,
                                   linhas, args.out)
    if montados != posicoes:
        raise SystemExit(f"ERRO: BOM da JLCPCB tem {montados} componentes mas o CPL "
                         f"tem {posicoes}; os dois precisam casar")
    print(f"   {len(linhas)} componentes, {refs} referencias, {montados} para montagem")

    montagem = {
        "total": len(linhas),
        "montados": montados,
        "nao_montados": len(linhas) - montados,
        "refs_total": refs,
        "refs_jlcpcb": len({l["lcsc"] for l in linhas if l["montar_jlcpcb"]}),
    }

    print("-> gerando a previa camada a camada")
    previa_camadas(kicad_pcb, os.path.join(dir_fab, "Previa"), projeto, versao)

    print("-> gerando o pinout")
    pinout.escrever(board, os.path.join(dir_fab, "PINOUT.md"), params, versao)

    print("-> anexando o esquema")
    tem_esquema = copiar_esquema(params, os.path.join(dir_esq, nomes["esquema"]))

    escrever_instrucoes(os.path.join(dir_fab, "INSTRUCOES-FABRICACAO.md"),
                        params, medidas, montagem, versao, nomes)

    if not args.sem_render:
        print("-> renderizando as imagens")
        renderizar(kicad_pcb, os.path.join(args.out, "img"))

    pacote = os.path.join(args.out, nomes["zip"])
    zipar(dir_fab, pacote)
    print(f"-> {pacote}")

    # Copias de nome estavel: sao elas que sustentam o link
    # /releases/latest/download/... do README, que nao pode mudar a cada versao.
    dir_estavel = os.path.join(args.out, "estavel")
    os.makedirs(dir_estavel, exist_ok=True)
    estaveis = {
        f"{projeto}-fab-latest.zip": pacote,
        f"{projeto}-bom-latest.csv": os.path.join(dir_mont, nomes["bom"]),
        f"{projeto}-jlcpcb-bom-latest.csv": os.path.join(dir_mont, nomes["bom_jlcpcb"]),
        f"{projeto}-jlcpcb-cpl-latest.csv": os.path.join(dir_mont, nomes["cpl"]),
    }
    if tem_esquema:
        estaveis[f"{projeto}-esquema-latest.pdf"] = os.path.join(dir_esq, nomes["esquema"])
    for estavel, origem_arq in estaveis.items():
        shutil.copy2(origem_arq, os.path.join(dir_estavel, estavel))

    medidas.update({"furos_fora_do_contorno": furos_fora, "projeto": projeto, "versao": versao, "commit": args.commit,
                    "revisao": params["revisao"], "montagem": montagem,
                    "nomes": nomes, "estaveis": sorted(estaveis),
                    "tem_esquema": tem_esquema, "avisos": avisos,
                    "casa_montagem": params["montagem"]["casa"],
                    "lado_smt": params["montagem"]["lado_smt"],
                    "legendas": params.get("legendas", {})})
    json.dump(medidas, open(os.path.join(args.out, "meta.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
