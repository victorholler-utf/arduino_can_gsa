#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAF CF - Replay & Offline DBC Decoder
=====================================
Permite decodificar (ou re-decodificar) arquivos brutos 'raw_can_*.csv'
já gravados utilizando novos ou atualizados arquivos .dbc.
Gera um novo CSV completo com todos os sinais mapeados.
"""

import os
import sys
import glob
import argparse
import csv
from datetime import datetime
import cantools
from colorama import init, Fore

init(autoreset=True)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def parse_j1939_id(can_id):
    priority = (can_id >> 26) & 0x7
    dp = (can_id >> 24) & 0x1
    pf = (can_id >> 16) & 0xFF
    ps = (can_id >> 8) & 0xFF
    sa = can_id & 0xFF

    if pf < 240:
        pgn = (dp << 16) | (pf << 8)
    else:
        pgn = (dp << 16) | (pf << 8) | ps

    return {"pgn": pgn, "sa": sa, "priority": priority}

def main():
    parser = argparse.ArgumentParser(description="Re-decodificador offline de logs CAN usando DBC")
    parser.add_argument("--raw", "-r", required=False, help="Caminho do arquivo raw_can_*.csv. Se omitido, pega o mais recente.")
    parser.add_argument("--dbc", "-d", default="../dbc", help="Pasta com arquivos .dbc (padrão: ../dbc)")
    parser.add_argument("--output", "-o", help="Caminho do arquivo CSV de saída (opcional)")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    dbc_dir = os.path.abspath(os.path.join(base_dir, args.dbc)) if not os.path.isabs(args.dbc) else args.dbc
    logs_dir = os.path.abspath(os.path.join(base_dir, "../logs"))

    # Localiza arquivo raw mais recente se não foi fornecido
    raw_path = args.raw
    if not raw_path:
        csv_files = sorted(glob.glob(os.path.join(logs_dir, "raw_can_*.csv")), key=os.path.getmtime, reverse=True)
        if not csv_files:
            print(Fore.RED + f"[ERRO] Nenhum arquivo 'raw_can_*.csv' encontrado em {logs_dir}")
            sys.exit(1)
        raw_path = csv_files[0]
        print(Fore.CYAN + f"[*] Usando o arquivo de log mais recente: {os.path.basename(raw_path)}")
    else:
        raw_path = os.path.abspath(raw_path)

    if not os.path.exists(raw_path):
        print(Fore.RED + f"[ERRO] Arquivo não encontrado: {raw_path}")
        sys.exit(1)

    # Carrega arquivos DBC
    dbc_files = glob.glob(os.path.join(dbc_dir, "*.dbc"))
    if not dbc_files:
        print(Fore.RED + f"[ERRO] Nenhum arquivo .dbc encontrado em: {dbc_dir}")
        sys.exit(1)

    print(Fore.CYAN + f"[*] Carregando arquivos DBC de {dbc_dir}...")
    combined_db = cantools.database.can.Database()
    for f in dbc_files:
        try:
            db = cantools.database.load_file(f)
            for msg in db.messages:
                try:
                    combined_db.messages.append(msg)
                except Exception:
                    pass
            print(Fore.GREEN + f"  [OK] {os.path.basename(f)} ({len(db.messages)} mensagens)")
        except Exception as e:
            print(Fore.RED + f"  [ERRO] Em {os.path.basename(f)}: {e}")

    # Define nome do arquivo de saída
    if args.output:
        out_path = os.path.abspath(args.output)
    else:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(raw_path))[0]
        out_path = os.path.join(logs_dir, f"redecoded_{base_name}_{timestamp_str}.csv")

    print(Fore.CYAN + f"[*] Processando {raw_path}...")
    print(Fore.CYAN + f"[*] Gravando resultado em: {out_path}")

    # Processa linhas
    total_rows = 0
    decoded_signals = 0

    with open(raw_path, "r", encoding="utf-8") as f_in, open(out_path, "w", encoding="utf-8", newline="") as f_out:
        reader = csv.DictReader(f_in)
        writer = csv.writer(f_out)
        writer.writerow(["Timestamp_ms", "DateTime", "CAN_ID_Hex", "PGN", "PGN_Hex", "Message_Name", "Signal_Name", "Value", "Unit"])

        for row in reader:
            total_rows += 1
            can_id_hex = row.get("CAN_ID_Hex", "")
            if not can_id_hex:
                continue

            try:
                can_id = int(can_id_hex, 16)
                data_hex = row.get("Data_Hex", "")
                data_bytes = bytes.fromhex(data_hex)
                ts_ms = row.get("Timestamp_ms", "")
                iso_time = row.get("DateTime", "")
                pgn = int(row.get("PGN", 0)) if "PGN" in row and row["PGN"] else parse_j1939_id(can_id)["pgn"]
            except Exception:
                continue

            # Decodificação
            decoded = None
            msg_name = ""
            msg = None

            try:
                msg = combined_db.get_message_by_frame_id(can_id)
                msg_name = msg.name
                decoded = msg.decode(data_bytes, decode_choices=False)
            except KeyError:
                for m in combined_db.messages:
                    m_j1939 = parse_j1939_id(m.frame_id)
                    if m_j1939["pgn"] == pgn:
                        try:
                            msg_name = m.name
                            msg = m
                            decoded = m.decode(data_bytes, decode_choices=False)
                            break
                        except Exception:
                            pass
            except Exception:
                pass

            if decoded and isinstance(decoded, dict):
                for sig_name, val in decoded.items():
                    decoded_signals += 1
                    unit = ""
                    if msg:
                        for s in msg.signals:
                            if s.name == sig_name:
                                unit = s.unit or ""
                                break
                    val_str = f"{val:.2f}" if isinstance(val, float) else str(val)
                    writer.writerow([ts_ms, iso_time, can_id_hex, pgn, f"{pgn:04X}", msg_name, sig_name, val_str, unit])

    print(Fore.GREEN + "=" * 60)
    print(Fore.GREEN + f"Processamento concluído!")
    print(Fore.GREEN + f"  Linhas RAW processadas:  {total_rows:,}")
    print(Fore.GREEN + f"  Sinais decodificados:    {decoded_signals:,}")
    print(Fore.GREEN + f"  Arquivo gerado:          {out_path}")
    print(Fore.GREEN + "=" * 60)

if __name__ == "__main__":
    main()
