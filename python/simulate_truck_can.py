#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulador de Teste CAN para DAF CF
==================================
Gera um arquivo de log simulado em 'logs/raw_can_sample.csv' contendo
frames reais J1939 de caminhão (RPM variando, Velocidade, Temperatura, etc.)
para testar o decodificador DBC e a geração de relatórios antes de ligar no caminhão.
"""

import os
import time
import math
from datetime import datetime

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def generate_sample_log():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.abspath(os.path.join(base_dir, "../logs"))
    os.makedirs(logs_dir, exist_ok=True)

    sample_file = os.path.join(logs_dir, "raw_can_sample.csv")
    print(f"[*] Gerando log de teste J1939 em: {sample_file}")

    with open(sample_file, "w", encoding="utf-8") as f:
        f.write("Timestamp_ms,DateTime,CAN_ID_Hex,Extended,DLC,Data_Hex,PGN,PGN_Hex,Source_Address,Priority\n")

        # Simula 60 segundos de caminhão ligado acelerando e desacelerando
        ts = 1000
        for i in range(120):
            t_sec = i * 0.5
            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # 1. EEC1: RPM (SPN 190, fator 0.125) - RPM oscilando entre 600 (lenta) e 1800 rpm
            rpm = 650 + int(600 * (1 + math.sin(t_sec * 0.2)))
            raw_rpm = int(rpm / 0.125)
            # Bytes 3 e 4 (0-indexed) de EEC1 carregam RPM (little endian)
            rpm_lsb = raw_rpm & 0xFF
            rpm_msb = (raw_rpm >> 8) & 0xFF
            eec1_data = f"FF007D{rpm_lsb:02X}{rpm_msb:02X}00FFFF"
            # CAN ID EEC1: 0x0CF00400 (PGN 61444 / 0xF004)
            f.write(f"{ts},{now_iso},0CF00400,1,8,{eec1_data},61444,F004,0,3\n")
            ts += 50

            # 2. CCVS: Velocidade (SPN 84, fator 1/256 km/h) - 0 a 85 km/h
            speed = max(0, int(45 + 35 * math.sin(t_sec * 0.1)))
            raw_speed = int(speed * 256)
            speed_lsb = raw_speed & 0xFF
            speed_msb = (raw_speed >> 8) & 0xFF
            # Byte 1 e 2 carregam velocidade
            ccvs_data = f"00{speed_lsb:02X}{speed_msb:02X}000000FFFF"
            # CAN ID CCVS: 0x18FEF100 (PGN 65265 / 0xFEF1)
            f.write(f"{ts},{now_iso},18FEF100,1,8,{ccvs_data},65265,FEF1,0,6\n")
            ts += 100

            # 3. ET1: Temperatura do motor (SPN 110, offset -40) - ~88 deg C
            temp = 88
            raw_temp = temp + 40
            et1_data = f"{raw_temp:02X}324545FFFFFFFF"
            # CAN ID ET1: 0x18FEEE00 (PGN 65262 / 0xFEEE)
            f.write(f"{ts},{now_iso},18FEEE00,1,8,{et1_data},65262,FEEE,0,6\n")
            ts += 350

    print(f"[OK] Arquivo de teste gerado com sucesso!")
    print(f"    Para testar o decodificador DBC execute:")
    print(f"    python python/replay_and_export.py --raw logs/raw_can_sample.csv")

if __name__ == "__main__":
    generate_sample_log()
