"""
NOME: Adenilton Ribeiro
DATA: 14/11/2026
PROJETO: workers.py
VERSAO: 1.0.0
DESCRICAO: - feat: Threads da interface: monitor serial do app e gravacao pelo bootloader
"""

import re
import time

from PyQt6.QtCore import QThread, pyqtSignal

from src.bootloader import Bootloader, BootError, Cancelled, program


# ========================================================================================================
# ---MONITOR SERIAL (mostra no log o que o app envia)---

class MonitorThread(QThread):
    line = pyqtSignal(str)          # linha recebida do app
    failed = pyqtSignal(str)        # porta caiu (ex.: cabo desconectado)

    def __init__(self, port):
        super().__init__()
        self.port = port
        self._stop = False

    def stop(self):
        self._stop = True
        self.wait(2000)

    def run(self):
        buf = ""
        last = time.monotonic()
        self.port.timeout = 0.1
        while not self._stop:
            try:
                data = self.port.read(256)
            except Exception as e:      # serial.SerialException, OSError
                if not self._stop:
                    self.failed.emit(str(e))
                return
            now = time.monotonic()
            if data:
                buf += data.decode("latin-1")
                last = now
                # aceita \n, \r\n, \n\r e \r como fim de linha (o uart.X usa "\n\r")
                parts = re.split(r"\r\n|\n\r|\n|\r", buf)
                buf = parts.pop()
                for ln in parts:
                    if ln:
                        self.line.emit(ln)
            elif buf and now - last > 0.3:      # linha sem fim de linha (ex.: prompt)
                self.line.emit(buf)
                buf = ""
        if buf:
            self.line.emit(buf)


# ========================================================================================================
# ---GRAVACAO---

class ProgramThread(QThread):
    log = pyqtSignal(str, str)          # (nivel, mensagem): info/ok/warn/err
    progress = pyqtSignal(int, int)     # (feito, total)
    done = pyqtSignal(bool, float)      # (sucesso?, tempo de gravacao em s)

    def __init__(self, port, image, boot_baud, wait_s, verify, dtr_reset, run_app=True):
        super().__init__()
        self.port = port
        self.image = image
        self.boot_baud = boot_baud
        self.wait_s = wait_s
        self.verify = verify
        self.dtr_reset = dtr_reset
        self.run_app = run_app
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        port = self.port
        old_baud = port.baudrate
        ok = False
        elapsed = 0.0
        try:
            port.baudrate = self.boot_baud
            if self.dtr_reset:
                port.dtr = True
                port.rts = True
                time.sleep(0.1)
                port.dtr = False
                port.rts = False
            self.log.emit("info", f"Aguardando o bootloader ({self.boot_baud} bps) - aperte o RESET da placa...")
            bl = Bootloader(port)
            ver = bl.connect(self.wait_s, should_stop=lambda: self._cancel)
            self.log.emit("ok", f"Bootloader v{ver >> 4}.{ver & 0xF} conectado. Gravando...")
            t0 = time.monotonic()
            program(bl, self.image, verify=self.verify,
                    progress=lambda d, t: self.progress.emit(d, t),
                    should_stop=lambda: self._cancel)
            elapsed = time.monotonic() - t0
            self.log.emit("ok", f"Gravacao{'' if not self.verify else ' e verificacao'} OK "
                                f"({len(self.image.rows)} linhas em {elapsed:.1f} s).")
            if self.run_app:
                bl.run()
                self.log.emit("ok", "Aplicacao rodando.")
            ok = True
        except Cancelled:
            self.log.emit("warn", "Gravacao cancelada. O PIC continua no bootloader: aperte RESET ou grave de novo.")
        except BootError as e:
            self.log.emit("err", f"ERRO: {e}")
        except Exception as e:          # porta caiu, etc.
            self.log.emit("err", f"ERRO: {e}")
        finally:
            try:
                port.baudrate = old_baud
                port.timeout = 0.1
                port.reset_input_buffer()
            except Exception:
                pass
            self.done.emit(ok, elapsed)
