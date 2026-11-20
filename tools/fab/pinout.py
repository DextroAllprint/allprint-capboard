#!/usr/bin/env python3
"""Gera o PINOUT.md da placa a partir das nets do PCB.

O pino a pino sai do .PcbDoc (pad -> net), nao do esquema: e o que esta de fato
no cobre. Entram:
    - os conectores (prefixos de 'pinout.conectores' em parametros.json);
    - os CIs com pelo menos 'pinout.ci_min_pinos' pinos (MCU, drivers, PHY...);
    - o que estiver em 'pinout.incluir', e sai o que estiver em 'pinout.excluir'.

Net sem nome no esquema (o Altium a batiza de NetJ1_1, o KiCad de Net-(U1-Pad3))
nao diz nada a quem esta com a placa na mao: no lugar do nome sai a lista de
pinos onde o sinal chega (ex.: '→ R10.1, U5.13'). Pad sem net vira 'NC'.
"""

import re

PADRAO = {
    "conectores": ["J", "P", "CN", "CON", "USB", "HDR", "RJ", "HDMI"],
    "ci_min_pinos": 20,
    "incluir": [],
    "excluir": [],
}


def _natural(texto):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", texto)]


SEM_NOME = re.compile(r"^(Net-\(|unconnected-|Net[A-Z]+[0-9]*[A-Z]?_[0-9A-Z]+$)")
MAX_DESTINOS = 4
_destinos = {}


def indexar(board):
    """net -> ['R10.1', 'U5.13', ...], para descrever as nets sem nome."""
    _destinos.clear()
    for fp in board.GetFootprints():
        ref = fp.GetReference().strip()
        if not ref:
            continue
        for pad in fp.Pads():
            if pad.GetNetname() and pad.GetNumber():
                _destinos.setdefault(pad.GetNetname(), []).append(f"{ref}.{pad.GetNumber()}")


def _net(pad, ref=""):
    nome = pad.GetNetname() or ""
    if not nome:
        return "NC"
    limpo = nome.lstrip("/")
    if not SEM_NOME.match(limpo):
        return f"`{limpo}`"
    proprio = f"{ref}.{pad.GetNumber()}"
    outros = sorted({d for d in _destinos.get(nome, []) if d != proprio and not d.startswith(ref + ".")},
                    key=_natural)
    if not outros:
        return "— (sem destino fora do componente)"
    extra = f" +{len(outros) - MAX_DESTINOS}" if len(outros) > MAX_DESTINOS else ""
    return "→ " + ", ".join(outros[:MAX_DESTINOS]) + extra


def _prefixo(ref):
    return re.match(r"[A-Za-z_]*", ref).group(0).upper()


def selecionar(board, cfg):
    conectores, cis = [], []
    prefixos = {p.upper() for p in cfg["conectores"]}
    for fp in board.GetFootprints():
        ref = fp.GetReference().strip()
        if not ref or ref in cfg["excluir"]:
            continue
        pads = [p for p in fp.Pads() if p.GetNumber()]
        if len(pads) < 2:
            continue
        if ref in cfg["incluir"] or _prefixo(ref) in prefixos:
            conectores.append(fp)
        elif _prefixo(ref) == "U" and len({p.GetNumber() for p in pads}) >= cfg["ci_min_pinos"]:
            cis.append(fp)
    chave = lambda f: _natural(f.GetReference())
    return sorted(conectores, key=chave), sorted(cis, key=chave)


def tabela(fp, so_ligados=False):
    """Linhas pino | net. Pads repetidos (ex.: carcaca, EP) viram uma linha so."""
    vistos = {}
    for pad in fp.Pads():
        numero = pad.GetNumber()
        if not numero:
            continue
        net = _net(pad, fp.GetReference())
        if numero in vistos and vistos[numero] != "NC":
            continue
        vistos[numero] = net
    linhas = sorted(vistos.items(), key=lambda kv: _natural(kv[0]))
    if so_ligados:
        linhas = [(n, net) for n, net in linhas if net != "NC"]
    return linhas


def _cabecalho(fp):
    lado = "bottom" if fp.IsFlipped() else "top"
    return (f"`{fp.GetValue()}` · footprint `{fp.GetFPIDAsString().split(':')[-1]}` "
            f"· lado {lado}")


def escrever(board, caminho, params, versao):
    cfg = dict(PADRAO)
    cfg.update(params.get("pinout", {}))
    indexar(board)
    conectores, cis = selecionar(board, cfg)

    linhas = [
        f"# Pinout — {params['projeto']}",
        "",
        f"Versao do pacote: **{versao}**. Gerado das nets do `.PcbDoc` pelo CI —",
        "nao editar a mao: o que esta aqui e o que esta no cobre.",
        "",
        "Sinal em `codigo` = nome da net no esquema. `→ R10.1, U5.13` = net sem nome:",
        "a lista e de onde o pino chega. `NC` = pino sem ligacao.",
        "",
    ]

    if conectores:
        linhas += ["## Conectores", ""]
        linhas += ["| Ref. | Peca | Pinos |", "| --- | --- | --- |"]
        for fp in conectores:
            linhas.append(f"| [{fp.GetReference()}](#{fp.GetReference().lower()}) | "
                          f"`{fp.GetValue()}` | {len(tabela(fp))} |")
        linhas.append("")
        for fp in conectores:
            linhas += [f"### {fp.GetReference()}", "", _cabecalho(fp), "",
                       "| Pino | Sinal |", "| --- | --- |"]
            linhas += [f"| {n} | {net} |" for n, net in tabela(fp)]
            linhas.append("")

    if cis:
        linhas += ["## Circuitos integrados", "",
                   f"CIs com {cfg['ci_min_pinos']} pinos ou mais. Pinos sem ligacao (NC) "
                   "ficam de fora; alimentacao e terra incluidos.", ""]
        for fp in cis:
            ligados = tabela(fp, so_ligados=True)
            linhas += [f"### {fp.GetReference()} — {fp.GetValue()}", "", _cabecalho(fp), "",
                       f"{len(ligados)} de {len(tabela(fp))} pinos ligados.", "",
                       "| Pino | Sinal |", "| --- | --- |"]
            linhas += [f"| {n} | {net} |" for n, net in ligados]
            linhas.append("")

    with open(caminho, "w") as fp:
        fp.write("\n".join(linhas))
    return len(conectores), len(cis)
