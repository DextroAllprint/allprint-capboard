#!/usr/bin/env python3
"""Le o .SchDoc do Altium e devolve a lista de componentes com seus parametros.

O KiCad nao ajuda aqui: o importador de .SchDoc dele so existe na GUI. Mas o
.SchDoc guarda os registros como blocos ASCII delimitados por '|', terminados em
NUL, entao da pra ler direto do binario sem depender do Altium.

Registros que interessam:
    RECORD=1    componente (LibReference, ComponentDescription)
    RECORD=34   designador do componente (Text=R1), ligado por OwnerIndex
    RECORD=41   parametro nomeado (Name=LCSC, Text=C17477), idem
    RECORD=45   modelo/footprint associado

OwnerIndex e a posicao ordinal do registro dono dentro do stream.
"""

import re


def _registros(caminho):
    dados = open(caminho, "rb").read()
    saida = []
    for achado in re.finditer(rb"\|RECORD=[^\x00]{0,4000}", dados):
        campos = {}
        for parte in achado.group(0).decode("latin1").split("|"):
            if "=" in parte:
                chave, _, valor = parte.partition("=")
                # Altium repete a chave em UTF8: '%UTF8%Nome' sobrepoe o ASCII.
                campos[chave.replace("%UTF8%", "")] = valor
        saida.append(campos)
    return saida


def componentes(caminho):
    """Devolve [{designador, comentario, biblioteca, descricao, parametros{}}]."""
    recs = _registros(caminho)
    donos = {i: r for i, r in enumerate(recs) if r.get("RECORD") == "1"}

    designadores, parametros, modelos = {}, {}, {}
    for reg in recs:
        tipo = reg.get("RECORD")
        indice = reg.get("OwnerIndex")
        if indice is None or not indice.lstrip("-").isdigit():
            continue
        indice = int(indice)
        if tipo == "34":
            designadores[indice] = reg.get("Text", "")
        elif tipo == "41" and reg.get("Name"):
            parametros.setdefault(indice, {})[reg["Name"]] = reg.get("Text", "")
        elif tipo == "45":
            modelos.setdefault(indice, []).append(
                reg.get("ModelName") or reg.get("Description", "")
            )

    saida = []
    for indice, comp in sorted(donos.items()):
        params = parametros.get(indice, {})
        saida.append({
            "designador": designadores.get(indice, ""),
            "comentario": params.get("Comment", "") or comp.get("LibReference", ""),
            "biblioteca": comp.get("LibReference", ""),
            "descricao": comp.get("ComponentDescription", ""),
            "lcsc": params.get("LCSC", ""),
            "parametros": params,
            "modelos": modelos.get(indice, []),
        })
    return [c for c in saida if c["designador"]]


if __name__ == "__main__":
    import sys, json
    print(json.dumps(componentes(sys.argv[1]), indent=2, ensure_ascii=False))
