#!/usr/bin/env python3
"""
NOME: Adenilton Ribeiro
DATA: 14/11/2026
PROJETO: pic16f88_boot.py
VERSAO: 1.1.0
DESCRICAO: - feat: Uploader do bootloader UART do PIC16F88 pelo terminal (Git Bash / cmd)
           - refactor: usa o nucleo em src/bootloader (o mesmo da interface grafica)

Uso:
    python scripts/pic16f88_boot.py --list
    python scripts/pic16f88_boot.py -p COM4 app.hex
    winpty python scripts/pic16f88_boot.py -p COM4 app.hex --monitor 9600    (Git Bash)

Depois de iniciar o comando, aperte o RESET da placa (o bootloader escuta por ~1 s apos o reset).
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bootloader import (HexError, BootError, Bootloader, load_image, program, APP_END)  # noqa: E402


def bar(done, total, t0):
    filled = "#" * (30 * done // total)
    sys.stdout.write(f"\r  [{filled:<30}] {done}/{total}  {time.monotonic() - t0:4.1f} s")
    sys.stdout.flush()
    if done == total:
        sys.stdout.write("\n")


def main():
    ap = argparse.ArgumentParser(description="Grava um .hex no PIC16F88 pelo bootloader UART.")
    ap.add_argument("hex", nargs="?", help="arquivo .hex gerado pelo MPLAB X (dist/default/production)")
    ap.add_argument("-p", "--port", help="porta serial (ex.: COM4, /dev/ttyUSB0)")
    ap.add_argument("-b", "--baud", type=int, default=19200, help="baud do bootloader (padrao 19200)")
    ap.add_argument("-t", "--wait", type=float, default=15.0, help="tempo esperando o RESET, em s (padrao 15)")
    ap.add_argument("--no-verify", action="store_true", help="nao le de volta para verificar")
    ap.add_argument("--no-run", action="store_true", help="nao roda o app ao final")
    ap.add_argument("--dtr-reset", action="store_true",
                    help="pulsa DTR/RTS antes de conectar (se o adaptador estiver ligado no MCLR por capacitor)")
    ap.add_argument("--monitor", type=int, metavar="BAUD",
                    help="depois de gravar, abre um terminal serial nesse baud (Ctrl+C para sair)")
    ap.add_argument("--list", action="store_true", help="lista as portas seriais")
    args = ap.parse_args()

    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        print("Instale o pyserial:  pip install pyserial")
        return 2

    if args.list:
        for p in serial.tools.list_ports.comports():
            print(f"{p.device:12s} {p.description}")
        return 0
    if not args.hex or not args.port:
        ap.error("informe o .hex e a porta (-p)")

    try:
        image = load_image(args.hex)
    except (HexError, OSError) as e:
        print(f"ERRO: {e}")
        return 1
    for w in image.warnings:
        print(f"AVISO: {w}")
    print(f"{args.hex}: {image.used_words} words de programa ({image.percent:.0f}% de {APP_END}), "
          f"{len(image.rows)} linhas, {len(image.eeprom)} bytes de EEPROM")

    try:
        port = serial.Serial(args.port, args.baud, timeout=1.0)
    except serial.SerialException as e:
        print(f"ERRO abrindo {args.port}: {e}")
        return 1

    try:
        if args.dtr_reset:
            port.dtr = True
            port.rts = True
            time.sleep(0.1)
            port.dtr = False
            port.rts = False
        print(f"Aguardando o bootloader em {args.port} - aperte o RESET da placa...")
        bl = Bootloader(port)
        ver = bl.connect(args.wait)
        print(f"Bootloader v{ver >> 4}.{ver & 0xF} conectado. Gravando...")
        t0 = time.monotonic()
        program(bl, image, verify=not args.no_verify, progress=lambda d, t: bar(d, t, t0))
        print("Gravacao" + ("" if args.no_verify else " e verificacao") + " OK.")
        if not args.no_run:
            bl.run()
            print("Aplicacao rodando.")
    except BootError as e:
        print(f"\nERRO: {e}")
        return 1
    finally:
        port.close()

    if args.monitor and not args.no_run:
        print(f"--- monitor {args.port} @ {args.monitor} (Ctrl+C para sair) ---")
        try:
            with serial.Serial(args.port, args.monitor, timeout=0.1) as mon:
                while True:
                    data = mon.read(256)
                    if data:
                        sys.stdout.write(data.decode("latin-1"))
                        sys.stdout.flush()
        except KeyboardInterrupt:
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
