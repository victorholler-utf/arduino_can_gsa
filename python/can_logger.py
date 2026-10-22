#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAF CF - CAN / J1939 / OBD-II Real-time Logger & Decoder
=========================================================
Leitura via Arduino + MCP2515 (8 MHz, 250 kbps J1939)
Salva logs automaticamente na pasta 'logs/' do projeto:
  1. raw_can_YYYYMMDD_HHMMSS.csv  -> Frames CAN brutos com breakdown de J1939 (PGN, SA, Priority)
  2. decoded_can_YYYYMMDD_HHMMSS.csv -> Sinais decodificados via arquivos .dbc
  3. can_log_YYYYMMDD_HHMMSS.asc  -> Formato Vector ASC (compatível com CANoe, SavvyCAN, etc.)
"""

import os
import sys
import time
import glob
import argparse
from datetime import datetime
import serial
import serial.tools.list_ports
import cantools
from colorama import init, Fore, Style

# Inicializa colorama para cores no terminal Windows
init(autoreset=True)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def find_arduino_port():
    """Detecta automaticamente portas seriais disponíveis."""
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "arduino" in desc or "ch340" in desc or "cp210" in desc or "usb-serial" in desc or "ftdi" in desc:
            return p.device
    # Se não achou nome explícito, retorna a primeira porta COM disponível
    return ports[0].device

def parse_j1939_id(can_id):
    """
    Decodifica o identificador CAN 29-bit de acordo com a norma SAE J1939:
    Priority (3 bits), DP (1 bit), PF (8 bits), PS (8 bits), SA (8 bits)
    """
    priority = (can_id >> 26) & 0x7
    edp = (can_id >> 25) & 0x1
    dp = (can_id >> 24) & 0x1
    pf = (can_id >> 16) & 0xFF
    ps = (can_id >> 8) & 0xFF
    sa = can_id & 0xFF

    # Cálculo do PGN (Parameter Group Number)
    if pf < 240:
        # PDU1 (endereçamento ponto a ponto): PS é Destination Address (DA)
        pgn = (dp << 16) | (pf << 8)
        da = ps
    else:
        # PDU2 (endereçamento broadcast): PS faz parte do PGN
        pgn = (dp << 16) | (pf << 8) | ps
        da = 255  # Broadcast

    return {
        "priority": priority,
        "edp": edp,
        "dp": dp,
        "pf": pf,
        "ps": ps,
        "sa": sa,
        "da": da,
        "pgn": pgn
    }

def load_dbc_databases(dbc_dir):
    """Carrega todos os arquivos .dbc presentes na pasta especificada."""
    dbc_files = glob.glob(os.path.join(dbc_dir, "*.dbc"))
    if not dbc_files:
        print(Fore.YELLOW + f"[AVISO] Nenhum arquivo .dbc encontrado em: {os.path.abspath(dbc_dir)}")
        print(Fore.YELLOW + "        Os logs continuarão sendo gravados em modo RAW (bruto).")
        print(Fore.YELLOW + "        Coloque seus arquivos DBC na pasta 'dbc/' para decodificação em tempo real.\n")
        return None

    combined_db = cantools.database.can.Database()
    loaded_count = 0

    print(Fore.CYAN + f"[*] Carregando arquivos DBC de: {os.path.abspath(dbc_dir)}")
    for dbc_file in dbc_files:
        try:
            db = cantools.database.load_file(dbc_file)
            for msg in db.messages:
                try:
                    combined_db.messages.append(msg)
                except Exception:
                    pass
            print(Fore.GREEN + f"  [OK] Carregado: {os.path.basename(dbc_file)} ({len(db.messages)} mensagens)")
            loaded_count += 1
        except Exception as e:
            print(Fore.RED + f"  [ERRO] Falha ao carregar {os.path.basename(dbc_file)}: {e}")

    print(Fore.CYAN + f"[*] Total de mensagens mapeadas: {len(combined_db.messages)}\n")
    return combined_db if loaded_count > 0 else None

def main():
    parser = argparse.ArgumentParser(description="DAF CF - CAN/J1939 Logger & Decoder")
    parser.add_argument("--port", "-p", help="Porta Serial COM (ex: COM3, COM4). Se omitido, tenta auto-detectar.")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baudrate da Serial (padrão: 115200)")
    parser.add_argument("--dbc", "-d", default="../dbc", help="Pasta com arquivos .dbc (padrão: ../dbc)")
    parser.add_argument("--logs", "-l", default="../logs", help="Pasta para salvar logs (padrão: ../logs)")
    args = parser.parse_args()

    # Normaliza caminhos relativos para o diretório raiz do projeto
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dbc_dir = os.path.abspath(os.path.join(base_dir, args.dbc)) if not os.path.isabs(args.dbc) else args.dbc
    logs_dir = os.path.abspath(os.path.join(base_dir, args.logs)) if not os.path.isabs(args.logs) else args.logs

    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(dbc_dir, exist_ok=True)

    print(Fore.CYAN + "=" * 65)
    print(Fore.CYAN + "     DAF CF CAN LOGGER & DECODER - J1939 / OBD-II")
    print(Fore.CYAN + "     Hardware: Arduino Uno/Nano + MCP2515 (8 MHz, 250 kbps)")
    print(Fore.CYAN + "=" * 65)

    # 1. Carrega bancos de dados DBC
    db = load_dbc_databases(dbc_dir)

    # 2. Localiza porta COM
    port = args.port
    if not port:
        port = find_arduino_port()
        if not port:
            print(Fore.RED + "[ERRO] Nenhuma porta COM encontrada! Conecte o Arduino na porta USB.")
            all_ports = list(serial.tools.list_ports.comports())
            if all_ports:
                print("Portas disponíveis:")
                for p in all_ports:
                    print(f" - {p.device}: {p.description}")
            sys.exit(1)
        print(Fore.GREEN + f"[*] Porta detectada automaticamente: {port}")
    else:
        print(Fore.GREEN + f"[*] Usando porta informada: {port}")

    # 3. Abre porta serial
    try:
        ser = serial.Serial(port, args.baud, timeout=1.0)
        time.sleep(2)  # Aguarda reset do Arduino ao abrir serial
        ser.reset_input_buffer()
    except Exception as e:
        print(Fore.RED + f"[ERRO] Falha ao abrir {port}: {e}")
        sys.exit(1)

    # 4. Prepara arquivos de log
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_csv_path = os.path.join(logs_dir, f"raw_can_{session_id}.csv")
    dec_csv_path = os.path.join(logs_dir, f"decoded_can_{session_id}.csv")
    asc_path = os.path.join(logs_dir, f"can_log_{session_id}.asc")

    print(Fore.YELLOW + f"[*] Arquivos de log nesta sessao:")
    print(f"    Raw CSV:     {raw_csv_path}")
    print(f"    Decoded CSV: {dec_csv_path}")
    print(f"    Vector ASC:  {asc_path}")
    print(Fore.CYAN + "-" * 65)
    print(Fore.GREEN + "[*] Gravando dados... Pressione Ctrl + C para encerrar e salvar.")
    print(Fore.CYAN + "-" * 65)

    f_raw = open(raw_csv_path, "w", encoding="utf-8", buffering=1)
    f_raw.write("Timestamp_ms,DateTime,CAN_ID_Hex,Extended,DLC,Data_Hex,PGN,PGN_Hex,Source_Address,Priority\n")

    f_dec = open(dec_csv_path, "w", encoding="utf-8", buffering=1)
    f_dec.write("Timestamp_ms,DateTime,CAN_ID_Hex,PGN,PGN_Hex,Message_Name,Signal_Name,Value,Unit\n")

    f_asc = open(asc_path, "w", encoding="utf-8", buffering=1)
    now_str = datetime.now().strftime("%a %b %d %I:%M:%S %p %Y")
    f_asc.write(f"date {now_str}\n")
    f_asc.write("base hex  timestamps absolute\n")
    f_asc.write("internal events logged\n")
    f_asc.write("// DAF CF CAN Logger Session\n")

    # Estatísticas
    total_frames = 0
    decoded_signals_count = 0
    start_time = time.time()
    last_stat_time = time.time()
    last_signals_view = {}

    try:
        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            # Comentários do Arduino
            if line.startswith("#"):
                print(Fore.LIGHTBLACK_EX + f"Arduino: {line}")
                continue

            # Protocolo do Arduino: CAN:timestamp,ext,id_hex,len,b0,b1,...
            if line.startswith("CAN:"):
                parts = line[4:].split(",")
                if len(parts) < 4:
                    continue

                try:
                    ts_ms = int(parts[0])
                    is_ext = parts[1] == "1"
                    can_id_hex = parts[2]
                    can_id = int(can_id_hex, 16)
                    dlc = int(parts[3])
                    data_bytes = bytes([int(b, 16) for b in parts[4:4 + dlc]])
                    data_hex = "".join(f"{b:02X}" for b in data_bytes)
                except ValueError:
                    continue

                total_frames += 1
                iso_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                # J1939 decode helper
                j1939_info = parse_j1939_id(can_id) if is_ext else {"pgn": 0, "sa": 0, "priority": 0}
                pgn = j1939_info["pgn"]
                sa = j1939_info["sa"]
                prio = j1939_info["priority"]

                # 1. Salva no RAW CSV
                f_raw.write(f"{ts_ms},{iso_time},{can_id_hex},{1 if is_ext else 0},{dlc},{data_hex},{pgn},{pgn:04X},{sa},{prio}\n")

                # 2. Salva no Vector ASC
                # Formato: timestamp_sec channel id_hex(x se ext) Rx d len data_bytes
                sec_rel = (time.time() - start_time)
                ext_char = "x" if is_ext else ""
                data_space = " ".join(f"{b:02X}" for b in data_bytes)
                f_asc.write(f" {sec_rel:10.4f} 1  {can_id_hex:>8}{ext_char}   Rx   d {dlc} {data_space}\n")

                # 3. Decodificação via DBC (se houver DBC carregado)
                if db:
                    decoded = None
                    msg_name = ""
                    # Tenta decodificar pelo CAN ID exato
                    try:
                        msg = db.get_message_by_frame_id(can_id)
                        msg_name = msg.name
                        decoded = msg.decode(data_bytes, decode_choices=False)
                    except KeyError:
                        # Se não achou pelo ID completo em J1939, tenta buscar pelo PGN mascarando SA e Prioridade
                        for m in db.messages:
                            # Compara PGN se for mensagem J1939 de 29-bits
                            m_j1939 = parse_j1939_id(m.frame_id)
                            if m_j1939["pgn"] == pgn:
                                try:
                                    msg_name = m.name
                                    decoded = m.decode(data_bytes, decode_choices=False)
                                    break
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    if decoded and isinstance(decoded, dict):
                        for sig_name, val in decoded.items():
                            decoded_signals_count += 1
                            # Procura unidade do sinal
                            unit = ""
                            try:
                                for s in msg.signals:
                                    if s.name == sig_name:
                                        unit = s.unit or ""
                                        break
                            except Exception:
                                pass

                            val_str = f"{val:.2f}" if isinstance(val, float) else str(val)
                            f_dec.write(f"{ts_ms},{iso_time},{can_id_hex},{pgn},{pgn:04X},{msg_name},{sig_name},{val_str},{unit}\n")
                            last_signals_view[sig_name] = f"{val_str} {unit}".strip()

                # Dashboard no terminal a cada 1 segundo
                cur_time = time.time()
                if cur_time - last_stat_time >= 1.0:
                    fps = total_frames / (cur_time - start_time)
                    stat_line = f"Frames: {total_frames:,} | Taxa: {fps:.1f} msg/s | Sinais DBC: {decoded_signals_count:,} | Tempo: {int(cur_time - start_time)}s"
                    
                    # Se tiver sinais decodificados recentes, mostra alguns na tela
                    preview_str = ""
                    if last_signals_view:
                        sample_items = list(last_signals_view.items())[-3:]
                        preview_str = " | " + " ; ".join(f"{k}: {v}" for k, v in sample_items)

                    sys.stdout.write(f"\r{Fore.GREEN}[LOGANDO] {stat_line}{Fore.CYAN}{preview_str}  \033[K")
                    sys.stdout.flush()
                    last_stat_time = cur_time

    except KeyboardInterrupt:
        print("\n" + Fore.YELLOW + "[*] Finalizando gravaçao e salvando arquivos...")
    finally:
        ser.close()
        f_raw.close()
        f_dec.close()
        f_asc.close()

        print(Fore.GREEN + "=" * 65)
        print(Fore.GREEN + "           SESSAO ENCERRADA COM SUCESSO!")
        print(Fore.GREEN + f"  Total de Mensagens CAN recebidas: {total_frames:,}")
        print(Fore.GREEN + f"  Total de Sinais decodificados:    {decoded_signals_count:,}")
        print(Fore.GREEN + f"  Logs salvos na pasta:             {logs_dir}")
        print(Fore.GREEN + "=" * 65)

if __name__ == "__main__":
    main()
