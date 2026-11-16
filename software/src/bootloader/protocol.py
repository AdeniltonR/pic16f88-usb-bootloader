"""
NOME: Adenilton Ribeiro
DATA: 14/11/2026
PROJETO: protocol.py
VERSAO: 1.0.0
DESCRICAO: - feat: Protocolo do bootloader UART do PIC16F88 (sincronismo, grava, le, EEPROM, run)
"""

import time

from .hexfile import ROW_WORDS, BL_STUB, BLANK

# ========================================================================================================
# ---PROTOCOLO (precisa bater com bootloader.s)---

SYNC = 0x55
ACK, NAK, PROT = b"K", b"N", b"P"


class BootError(Exception):
    pass


class Cancelled(BootError):
    pass


class Bootloader:
    """Fala com o bootloader numa porta tipo pyserial (write/read/timeout/reset_input_buffer)."""

    def __init__(self, port, sleep=time.sleep, clock=time.monotonic):
        self.port = port
        self.sleep = sleep
        self.clock = clock
        self.version = None

    def _read(self, n, what):
        data = self.port.read(n)
        if len(data) != n:
            raise BootError(f"sem resposta do bootloader ({what})")
        return data

    def connect(self, wait_s, should_stop=None):
        """Envia 0x55 repetidamente ate o bootloader responder 'K' + versao."""
        self.port.reset_input_buffer()
        t0 = self.clock()
        self.port.timeout = 0.02
        found = False
        while self.clock() - t0 < wait_s:
            if should_stop and should_stop():
                raise Cancelled("cancelado")
            self.port.write(bytes([SYNC]))
            resp = self.port.read(2)
            if len(resp) >= 1 and resp[0:1] == ACK:
                found = True
                break
        if not found:
            raise BootError("bootloader nao respondeu (apertou o RESET? porta/baud corretos?)")
        # descarta respostas dos 0x55 extras e confirma
        self.sleep(0.1)
        self.port.reset_input_buffer()
        self.port.timeout = 1.0
        self.port.write(bytes([SYNC]))
        resp = self._read(2, "sincronismo")
        if resp[0:1] != ACK:
            raise BootError(f"resposta inesperada no sincronismo: {resp!r}")
        self.version = resp[1]
        return self.version

    def write_row(self, addr, row):
        payload = bytes([addr >> 8, addr & 0xFF])
        for w in row:
            payload += bytes([w & 0xFF, (w >> 8) & 0x3F])
        chk = (-sum(payload)) & 0xFF
        self.port.write(b"W" + payload + bytes([chk]))
        resp = self._read(1, f"gravacao 0x{addr:04X}")
        if resp == NAK:
            raise BootError(f"erro de checksum na linha 0x{addr:04X}")
        if resp == PROT:
            raise BootError(f"linha 0x{addr:04X} protegida")
        if resp != ACK:
            raise BootError(f"resposta inesperada na linha 0x{addr:04X}: {resp!r}")

    def read_row(self, addr):
        self.port.write(bytes([ord("R"), addr >> 8, addr & 0xFF]))
        raw = self._read(2 * ROW_WORDS, f"leitura 0x{addr:04X}")
        return [raw[2 * i] | (raw[2 * i + 1] << 8) for i in range(ROW_WORDS)]

    def write_ee(self, addr, value):
        payload = bytes([addr, value])
        self.port.write(b"D" + payload + bytes([(-sum(payload)) & 0xFF]))
        resp = self._read(1, f"EEPROM 0x{addr:02X}")
        if resp != ACK:
            raise BootError(f"erro gravando EEPROM 0x{addr:02X}: {resp!r}")

    def read_ee(self, addr):
        self.port.write(bytes([ord("E"), addr]))
        return self._read(1, f"leitura EEPROM 0x{addr:02X}")[0]

    def run(self):
        self.port.write(b"G")
        if self._read(1, "run") != ACK:
            raise BootError("bootloader nao confirmou o comando run")


def program(bl, image, verify=True, progress=None, should_stop=None):
    """Grava a imagem. progress(feito, total) e chamado a cada linha/byte."""
    rows = image.rows
    total = len(rows) + len(image.eeprom) + 2
    done = 0

    def step():
        nonlocal done
        done += 1
        if progress:
            progress(done, total)
        if should_stop and should_stop():
            raise Cancelled("cancelado")

    def put(addr, row):
        bl.write_row(addr, row)
        if verify:
            back = bl.read_row(addr)
            if back != row:
                bad = next(i for i in range(ROW_WORDS) if back[i] != row[i])
                raise BootError(f"verificacao falhou em 0x{addr + bad:04X}: "
                                f"lido 0x{back[bad]:04X}, esperado 0x{row[bad]:04X}")
        step()

    # 1) invalida o app (stub apagado: se cair a energia no meio, o PIC fica no bootloader)
    put(BL_STUB, [BLANK] * ROW_WORDS)
    # 2) grava o app
    for addr in sorted(rows):
        put(addr, rows[addr])
    # 3) EEPROM de dados
    for a in sorted(image.eeprom):
        bl.write_ee(a, image.eeprom[a])
        if verify and bl.read_ee(a) != image.eeprom[a]:
            raise BootError(f"verificacao da EEPROM falhou em 0x{a:02X}")
        step()
    # 4) por ultimo, o stub valida o app
    put(BL_STUB, image.stub)
