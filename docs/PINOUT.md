# Pinout — ALLPRINT-CAPBOARD-677512

Versao do pacote: **revA-20261120-b001f37**. Gerado das nets do `.PcbDoc` pelo CI —
nao editar a mao: o que esta aqui e o que esta no cobre.

Sinal em `codigo` = nome da net no esquema. `→ R10.1, U5.13` = net sem nome:
a lista e de onde o pino chega. `NC` = pino sem ligacao.

## Conectores

| Ref. | Peca | Pinos |
| --- | --- | --- |
| [J1](#j1) | `STLZ950/3G-5.08-V-GREEN_1` | 3 |
| [J2](#j2) | `DSHP04TS-S` | 8 |
| [J3](#j3) | `MCFPL-08` | 8 |
| [J4](#j4) | `MCFPL-04` | 4 |
| [J5](#j5) | `MCFPL-12` | 12 |
| [J6](#j6) | `MCFPL-08` | 8 |
| [J7](#j7) | `MCFPL-06` | 6 |
| [J8](#j8) | `MCFPL-10` | 10 |
| [J9](#j9) | `PEMC1-04` | 4 |
| [J10](#j10) | `PEMC1-02` | 2 |

### J1

`STLZ950/3G-5.08-V-GREEN_1` · footprint `STLZ950/3G-5.08-V` · lado top

| Pino | Sinal |
| --- | --- |
| 1 | `NF0` |
| 2 | `CM0` |
| 3 | `NA0` |

### J2

`DSHP04TS-S` · footprint `SW-SMD_8P-L6.7-W5.4-P1.27-LS8.5` · lado top

| Pino | Sinal |
| --- | --- |
| 1 | → R2.1, R3.2 |
| 2 | → R1.1, R4.2 |
| 3 | `O_RS485_P` |
| 4 | `O_RS485_N` |
| 5 | `H_RS485_N` |
| 6 | `H_RS485_P` |
| 7 | `GND` |
| 8 | `GND` |

### J3

`MCFPL-08` · footprint `MCFPL-08` · lado top

| Pino | Sinal |
| --- | --- |
| 1 | `GND` |
| 2 | `OUT_SYNC` |
| 3 | `OUT_LED` |
| 4 | `H_RS485_N` |
| 5 | → F1.1, J4.3, J5.7, J6.5 +2 |
| 6 | `Y00` |
| 7 | `X00` |
| 8 | `H_RS485_P` |

### J4

`MCFPL-04` · footprint `MCFPL-04` · lado top

| Pino | Sinal |
| --- | --- |
| 1 | `GND` |
| 2 | `INDEX` |
| 3 | → F1.1, J3.5, J5.7, J6.5 +2 |
| 4 | `INDEX'` |

### J5

`MCFPL-12` · footprint `MCFPL-12` · lado top

| Pino | Sinal |
| --- | --- |
| 1 | `GND` |
| 2 | `X01` |
| 3 | `X02` |
| 4 | `X03` |
| 5 | `X04` |
| 6 | `X05` |
| 7 | → F1.1, J3.5, J4.3, J6.5 +2 |
| 8 | `Y01` |
| 9 | `Y02` |
| 10 | `Y03` |
| 11 | `Y04` |
| 12 | `Y05` |

### J6

`MCFPL-08` · footprint `MCFPL-08` · lado top

| Pino | Sinal |
| --- | --- |
| 1 | `GND` |
| 2 | `GND` |
| 3 | `EN2` |
| 4 | `ISO_PGM_E` |
| 5 | → F1.1, J3.5, J4.3, J5.7 +2 |
| 6 | `EN0` |
| 7 | `EN1` |
| 8 | `ISO_PGM_C` |

### J7

`MCFPL-06` · footprint `MCFPL-06` · lado top

| Pino | Sinal |
| --- | --- |
| 1 | `GND` |
| 2 | `RS485_N` |
| 3 | `O_RS485_P` |
| 4 | → F1.1, J3.5, J4.3, J5.7 +2 |
| 5 | `RS485_P` |
| 6 | `O_RS485_N` |

### J8

`MCFPL-10` · footprint `MCFPL-10` · lado top

| Pino | Sinal |
| --- | --- |
| 1 | `SM_ENC_Z` |
| 2 | `SM_ENC_B` |
| 3 | `SM_ENC_A` |
| 4 | `GND` |
| 5 | `GND` |
| 6 | `BMA1` |
| 7 | `BMA2` |
| 8 | `BMB2` |
| 9 | `BMB1` |
| 10 | → F1.1, J3.5, J4.3, J5.7 +2 |

### J9

`PEMC1-04` · footprint `PEMC1-04` · lado top

| Pino | Sinal |
| --- | --- |
| 1 | → R9.1, R10.1 |
| 2 | `GND` |
| 3 | `EXP_SDA` |
| 4 | `EXP_SCL` |

### J10

`PEMC1-02` · footprint `PEMC1-02` · lado top

| Pino | Sinal |
| --- | --- |
| 1 | → R21.2 |
| 2 | → R23.2, R25.1, U5.4 |

## Circuitos integrados

CIs com 20 pinos ou mais. Pinos sem ligacao (NC) ficam de fora; alimentacao e terra incluidos.

### U1 — STM32G431CBT6

`STM32G431CBT6` · footprint `LQFP-48` · lado top

47 de 48 pinos ligados.

| Pino | Sinal |
| --- | --- |
| 1 | `3,3V` |
| 2 | → R44.1 |
| 3 | → R106.1 |
| 5 | `OSC_IN` |
| 6 | `OSC_OUT` |
| 7 | `RST` |
| 8 | → R28.1 |
| 9 | → U7.2, U7.3 |
| 10 | → U7.4 |
| 11 | → R30.1 |
| 12 | → U9.2 |
| 13 | → U9.4 |
| 14 | → U9.6 |
| 15 | → U9.8 |
| 16 | → R18.2 |
| 17 | → R3.1, R6.2 |
| 18 | → R4.1, R5.1 |
| 19 | `GND` |
| 20 | → C6.2, C9.2, R7.2 |
| 21 | `3,3V` |
| 22 | → U8.4 |
| 23 | `GND` |
| 24 | `3,3V` |
| 25 | → R32.1 |
| 26 | `CS` |
| 27 | `CLK` |
| 28 | `MISO` |
| 29 | `MOSI` |
| 30 | → R59.1, U10.15 |
| 31 | → R58.1, U10.14 |
| 32 | → U9.10 |
| 33 | → U9.12 |
| 34 | → R37.2 |
| 35 | `GND` |
| 36 | `3,3V` |
| 37 | `SWDIO` |
| 38 | `SWCLK` |
| 39 | `EXP_SCL` |
| 40 | `SWO` |
| 41 | → R42.2 |
| 42 | → U14.4 |
| 43 | → U14.8 |
| 44 | `EXP_SDA` |
| 45 | → U14.12 |
| 46 | → U8.2, U8.3 |
| 47 | `GND` |
| 48 | `3,3V` |

### U12 — TMC5160A-TA-T

`TMC5160A-TA-T` · footprint `TQFP-48_L7.0-W7.0-P0.50-LS9.0-BL-EP` · lado top

45 de 49 pinos ligados.

| Pino | Sinal |
| --- | --- |
| 1 | `HB1` |
| 2 | `CB1` |
| 3 | → C46.2 |
| 4 | → C38.2, C40.2, R60.1 |
| 5 | → C49.2, R68.1 |
| 6 | `GND` |
| 7 | `SRAL` |
| 8 | `SRAH` |
| 9 | `SRBH` |
| 10 | `SRBL` |
| 11 | `GND` |
| 12 | `GND` |
| 13 | `CS` |
| 14 | `CLK` |
| 15 | `MOSI` |
| 16 | `MISO` |
| 19 | `GND` |
| 20 | `3,3V` |
| 21 | → R61.1, R64.2 |
| 22 | `3,3V` |
| 23 | `ENCB` |
| 24 | `ENCA` |
| 25 | `ENCN` |
| 28 | `GND` |
| 29 | → C50.2, R68.2 |
| 30 | `GND` |
| 31 | → C42.1 |
| 32 | → C42.2 |
| 33 | → C38.2, C40.2, R60.1 |
| 34 | → C40.1 |
| 35 | `CA2` |
| 36 | `HA2` |
| 37 | → D28.2, R66.1 |
| 38 | `LA2` |
| 39 | `LA1` |
| 40 | → D27.2, R65.1 |
| 41 | `HA1` |
| 42 | `CA1` |
| 43 | `CB2` |
| 44 | `HB2` |
| 45 | → D30.2, R69.1 |
| 46 | `LB2` |
| 47 | `LB1` |
| 48 | → D29.2, R67.1 |
| 49 | `GND` |
