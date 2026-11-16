"""
NOME: Adenilton Ribeiro
DATA: 14/11/2026
PROJETO: helpers.py
VERSAO: 1.1.0
DESCRICAO: - feat: Funcoes auxiliares (configuracoes, log em arquivo, portas seriais)
           - feat: no executavel (.exe), config/ e data/logs/ ficam ao lado do .exe
"""

import json
import logging
import os
import sys
from datetime import datetime

# ========================================================================================================
# ---CAMINHOS---

if getattr(sys, "frozen", False):
    # executavel do PyInstaller: __file__ fica numa pasta temporaria, entao usa a pasta do .exe
    ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(ROOT, "config", "settings.json")
LOG_DIR = os.path.join(ROOT, "data", "logs")

DEFAULTS = {
    "bootloader_baud": 19200,       # fixo no firmware (SPBRG = 51 @ 16 MHz)
    "monitor_baud": 9600,           # baud do app mostrado no log
    "baud_options": [9600, 19200, 38400, 57600, 115200],
    "wait_reset_s": 15,             # tempo esperando o RESET da placa
    "verify": True,
    "dtr_reset": False,
    "last_port": "",
    "last_file": "",
    "last_program": "",             # texto da ultima gravacao (tempo e hora)
    "line_ending": "\r\n",          # fim de linha do campo de envio
    "log_timestamp": True,          # mostra a hora em cada linha do log
}


# ========================================================================================================
# ---CONFIGURACOES---

def load_settings():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_settings(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except OSError:
        pass


# ========================================================================================================
# ---LOG EM ARQUIVO (data/logs/bootloader_AAAAMMDD.log)---

def file_logger():
    logger = logging.getLogger("bootloader")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        name = os.path.join(LOG_DIR, f"bootloader_{datetime.now():%Y%m%d}.log")
        h = logging.FileHandler(name, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        logger.addHandler(h)
    except OSError:
        logger.addHandler(logging.NullHandler())
    return logger


# ========================================================================================================
# ---PORTAS SERIAIS---

def list_ports():
    """Retorna [(dispositivo, descricao)]."""
    from serial.tools import list_ports as lp
    return [(p.device, p.description) for p in sorted(lp.comports(), key=lambda p: p.device)]
