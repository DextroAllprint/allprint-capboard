# Previa dos Gerbers — ALLPRINT-CAPBOARD-677512

Versao do pacote: **revA-20261120-b001f37**.

Uma imagem por camada, renderizada do mesmo `.kicad_pcb` que gerou os
Gerbers. O contorno da placa (`Edge.Cuts`, o Mechanical 1 do Altium) esta
presente em **todas** elas, fixo, para servir de registro: qualquer camada
deslocada salta aos olhos na comparacao.

Conferir antes de mandar fabricar: contorno fechado, ausencia de cobre
invadindo a borda, silk fora de pad, e furacao dentro do contorno.

## Top Copper (`.gtl`)

Camada `F.Cu` sobre o contorno da placa.

![Top Copper](gerbers/F_Cu.png)

## Inner Copper 1 (`.g1`)

Camada `In1.Cu` sobre o contorno da placa.

![Inner Copper 1](In1_Cu.png)

## Inner Copper 2 (`.g2`)

Camada `In2.Cu` sobre o contorno da placa.

![Inner Copper 2](In2_Cu.png)

## Bottom Copper (`.gbl`)

Camada `B.Cu` sobre o contorno da placa.

![Bottom Copper](gerbers/B_Cu.png)

## Top Solder Mask (`.gts`)

Camada `F.Mask` sobre o contorno da placa.

![Top Solder Mask](gerbers/F_Mask.png)

## Bottom Solder Mask (`.gbs`)

Camada `B.Mask` sobre o contorno da placa.

![Bottom Solder Mask](gerbers/B_Mask.png)

## Top Silkscreen (`.gto`)

Camada `F.Silkscreen` sobre o contorno da placa.

![Top Silkscreen](gerbers/F_Silkscreen.png)

## Bottom Silkscreen (`.gbo`)

Camada `B.Silkscreen` sobre o contorno da placa.

![Bottom Silkscreen](gerbers/B_Silkscreen.png)

## Top Paste (`.gtp`)

Camada `F.Paste` sobre o contorno da placa.

![Top Paste](gerbers/F_Paste.png)

## Bottom Paste (`.gbp`)

Camada `B.Paste` sobre o contorno da placa.

![Bottom Paste](gerbers/B_Paste.png)

## Board Outline (`.gm1`)

Camada `Edge.Cuts` sobre o contorno da placa.

![Board Outline](gerbers/Edge_Cuts.png)
