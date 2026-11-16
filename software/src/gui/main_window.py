"""
NOME: Adenilton Ribeiro
DATA: 14/11/2026
PROJETO: main_window.py
VERSAO: 1.3.0
DESCRICAO: - feat: Janela principal do gravador (porta, baud, conectar, arquivo .hex, gravar, log)
           - feat: Campo para enviar comandos pela serial (com fim de linha e historico)
           - feat: Tempo da ultima gravacao abaixo da barra de progresso (a barra so mostra %)
           - feat: Caixa para ligar/desligar o timestamp das linhas do log
"""

import html
import os
from collections import deque
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton,
                             QVBoxLayout, QWidget)

from src.bootloader import HexError, load_image, APP_END
from src.utils import helpers
from .workers import MonitorThread, ProgramThread

APP_TITLE = "Bootloader PIC16F88"
APP_VERSION = "1.3.0"

LINE_ENDINGS = [("Nenhum", ""), ("LF (\\n)", "\n"), ("CR (\\r)", "\r"), ("CR+LF (\\r\\n)", "\r\n")]


class HistoryLineEdit(QLineEdit):
    """Campo de texto com historico (setas para cima/baixo), como num terminal."""

    def __init__(self):
        super().__init__()
        self.history = []
        self.pos = 0

    def add(self, text):
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self.pos = len(self.history)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Up and self.history:
            self.pos = max(0, self.pos - 1)
            self.setText(self.history[self.pos])
        elif e.key() == Qt.Key.Key_Down and self.history:
            self.pos = min(len(self.history), self.pos + 1)
            self.setText(self.history[self.pos] if self.pos < len(self.history) else "")
        else:
            super().keyPressEvent(e)


class MainWindow(QMainWindow):

    def __init__(self, theme, port_factory=None, list_ports=helpers.list_ports):
        super().__init__()
        self.theme = theme
        self.port_factory = port_factory
        self.list_ports_fn = list_ports
        self.cfg = helpers.load_settings()
        self.flog = helpers.file_logger()
        self.port = None
        self.monitor = None
        self.worker = None
        self.image = None
        self.entries = deque(maxlen=5000)     # (hora, nivel, texto) para redesenhar ao trocar o tema

        self.setWindowTitle(f"{APP_TITLE} v{APP_VERSION}")
        self.resize(760, 560)
        self.setAcceptDrops(True)
        self._build()
        self.theme.on_change = lambda c: self._on_theme()
        self.refresh_ports()
        if self.cfg.get("last_file") and os.path.isfile(self.cfg["last_file"]):
            self.set_file(self.cfg["last_file"])
        self._update_state()
        self.log("info", f"{APP_TITLE} v{APP_VERSION}. Escolha a porta, conecte e selecione o .hex.")

    # ====================================================================================================
    # ---MONTAGEM DA TELA---

    def _build(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setSpacing(10)

        # ---conexao---
        g_con = QGroupBox("Conexão")
        h = QHBoxLayout(g_con)
        h.addWidget(QLabel("Porta:"))
        self.cb_port = QComboBox()
        self.cb_port.setMinimumWidth(260)
        h.addWidget(self.cb_port, 1)
        self.bt_refresh = QPushButton("Atualizar")
        self.bt_refresh.setToolTip("Procura de novo as portas COM")
        self.bt_refresh.clicked.connect(self.refresh_ports)
        h.addWidget(self.bt_refresh)
        h.addSpacing(12)
        h.addWidget(QLabel("Baud:"))
        self.cb_baud = QComboBox()
        for b in self.cfg["baud_options"]:
            self.cb_baud.addItem(str(b), b)
        i = self.cb_baud.findData(self.cfg["monitor_baud"])
        self.cb_baud.setCurrentIndex(max(i, 0))
        self.cb_baud.setToolTip("Baud do monitor serial (o que o app envia aparece no log).\n"
                                f"Para gravar, o programa troca sozinho para {self.cfg['bootloader_baud']} bps.")
        self.cb_baud.currentIndexChanged.connect(self._baud_changed)
        h.addWidget(self.cb_baud)
        h.addSpacing(12)
        self.bt_connect = QPushButton("Conectar")
        self.bt_connect.setObjectName("primary")
        self.bt_connect.clicked.connect(self.toggle_connection)
        h.addWidget(self.bt_connect)
        root.addWidget(g_con)

        # ---gravacao---
        g_prog = QGroupBox("Gravação")
        v = QVBoxLayout(g_prog)
        hf = QHBoxLayout()
        hf.addWidget(QLabel("Arquivo:"))
        self.ed_file = QLineEdit()
        self.ed_file.setReadOnly(True)
        self.ed_file.setPlaceholderText("Selecione o .hex (dist/default/production) ou arraste para a janela")
        hf.addWidget(self.ed_file, 1)
        self.bt_browse = QPushButton("Procurar...")
        self.bt_browse.clicked.connect(self.browse)
        hf.addWidget(self.bt_browse)
        v.addLayout(hf)

        self.lb_info = QLabel("Nenhum arquivo selecionado.")
        v.addWidget(self.lb_info)

        ho = QHBoxLayout()
        self.ck_verify = QCheckBox("Verificar após gravar")
        self.ck_verify.setChecked(bool(self.cfg["verify"]))
        ho.addWidget(self.ck_verify)
        self.ck_dtr = QCheckBox("Reset por DTR")
        self.ck_dtr.setToolTip("Pulsa DTR/RTS antes de gravar (só funciona se o DTR do adaptador "
                               "estiver ligado ao MCLR por um capacitor)")
        self.ck_dtr.setChecked(bool(self.cfg["dtr_reset"]))
        ho.addWidget(self.ck_dtr)
        ho.addStretch(1)
        self.bt_cancel = QPushButton("Cancelar")
        self.bt_cancel.clicked.connect(self.cancel)
        ho.addWidget(self.bt_cancel)
        self.bt_program = QPushButton("Gravar")
        self.bt_program.setObjectName("primary")
        self.bt_program.setMinimumWidth(110)
        self.bt_program.clicked.connect(self.start_program)
        ho.addWidget(self.bt_program)
        v.addLayout(ho)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        v.addWidget(self.progress)
        self.lb_last = QLabel()
        last = self.cfg.get("last_program")
        self.lb_last.setText(f"Última gravação: {last}" if last else "Última gravação: -")
        v.addWidget(self.lb_last)
        root.addWidget(g_prog)

        # ---log---
        g_log = QGroupBox("Log")
        vl = QVBoxLayout(g_log)
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumBlockCount(5000)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(max(mono.pointSize(), 9))
        self.txt_log.setFont(mono)
        vl.addWidget(self.txt_log)
        hl = QHBoxLayout()
        self.ed_send = HistoryLineEdit()
        self.ed_send.setPlaceholderText("Comando para enviar ao PIC (Enter envia, setas = histórico)")
        self.ed_send.returnPressed.connect(self.send_command)
        hl.addWidget(self.ed_send, 1)
        self.cb_eol = QComboBox()
        for name, eol in LINE_ENDINGS:
            self.cb_eol.addItem(name, eol)
        i = self.cb_eol.findData(self.cfg.get("line_ending", "\r\n"))
        self.cb_eol.setCurrentIndex(max(i, 0))
        self.cb_eol.setToolTip("Fim de linha acrescentado ao comando")
        hl.addWidget(self.cb_eol)
        self.bt_send = QPushButton("Enviar")
        self.bt_send.clicked.connect(self.send_command)
        hl.addWidget(self.bt_send)
        hl.addSpacing(12)
        self.ck_ts = QCheckBox("Timestamp")
        self.ck_ts.setToolTip("Mostra a hora em cada linha do log")
        self.ck_ts.setChecked(bool(self.cfg.get("log_timestamp", True)))
        self.ck_ts.toggled.connect(self._ts_toggled)
        hl.addWidget(self.ck_ts)
        self.bt_clear = QPushButton("Limpar log")
        self.bt_clear.clicked.connect(self.clear_log)
        hl.addWidget(self.bt_clear)
        vl.addLayout(hl)
        root.addWidget(g_log, 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Desconectado")

    # ====================================================================================================
    # ---LOG---

    def log(self, level, msg):
        """level: info / ok / warn / err / app (texto vindo do PIC) / tx (texto enviado ao PIC)."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.entries.append((ts, level, msg))
        self.txt_log.appendHtml(self._fmt(ts, level, msg))
        self.flog.info(f"[{level}] {msg}")

    def _fmt(self, ts, level, msg):
        c = self.theme.colors
        color = {"info": c["log_info"], "ok": c["log_ok"], "warn": c["log_warn"],
                 "err": c["log_err"], "app": c["log_app"], "tx": c["log_tx"]}[level]
        tag = {"app": "PIC >", "tx": "TX  >"}.get(level, "")
        show_ts = self.ck_ts.isChecked() if hasattr(self, "ck_ts") else True
        prefix = " ".join(x for x in ((ts if show_ts else ""), tag) if x)
        if not prefix:
            return f'<span style="color:{color}">{html.escape(msg)}</span>'
        prefix = prefix.replace(" ", "&nbsp;")
        return (f'<span style="color:{c["disabled"]}">{prefix}</span> '
                f'<span style="color:{color}">{html.escape(msg)}</span>')

    def clear_log(self):
        self.entries.clear()
        self.txt_log.clear()

    def _ts_toggled(self, on):
        self.cfg["log_timestamp"] = on
        self._redraw_log()

    def _on_theme(self):
        self._redraw_log()

    def _redraw_log(self):
        # redesenha o log (troca de tema ou de timestamp)
        self.txt_log.clear()
        for e in self.entries:
            self.txt_log.appendHtml(self._fmt(*e))

    # ====================================================================================================
    # ---PORTAS---

    def refresh_ports(self):
        current = self.cb_port.currentData() or self.cfg.get("last_port")
        self.cb_port.clear()
        try:
            ports = self.list_ports_fn()
        except Exception as e:
            ports = []
            self.log("err", f"Erro listando portas: {e}")
        for dev, desc in ports:
            self.cb_port.addItem(f"{dev} - {desc}" if desc and desc != dev else dev, dev)
        if current:
            i = self.cb_port.findData(current)
            if i >= 0:
                self.cb_port.setCurrentIndex(i)
        if not ports:
            self.cb_port.addItem("(nenhuma porta encontrada)", None)
        self._update_state()

    def toggle_connection(self):
        if self.port:
            self.disconnect_port()
        else:
            self.connect_port()

    def connect_port(self):
        dev = self.cb_port.currentData()
        if not dev:
            self.log("warn", "Nenhuma porta selecionada.")
            return
        baud = self.cb_baud.currentData()
        try:
            factory = self.port_factory
            if factory is None:
                import serial
                factory = serial.Serial
            self.port = factory(dev, baud, timeout=0.1)
        except Exception as e:
            self.port = None
            self.log("err", f"Não foi possível abrir {dev}: {e}")
            self.log("warn", "Verifique se outro programa (terminal, MPLAB, PuTTY) está usando a porta.")
            return
        self.cfg["last_port"] = dev
        self.log("ok", f"Conectado em {dev} a {baud} bps. O que o PIC enviar aparece aqui.")
        self._start_monitor()
        self._update_state()

    def disconnect_port(self):
        self._stop_monitor()
        if self.port:
            try:
                self.port.close()
            except Exception:
                pass
            self.log("info", "Desconectado.")
        self.port = None
        self._update_state()

    def _baud_changed(self):
        baud = self.cb_baud.currentData()
        self.cfg["monitor_baud"] = baud
        if self.port and not self.worker:
            try:
                self.port.baudrate = baud
                self.log("info", f"Monitor em {baud} bps.")
            except Exception as e:
                self.log("err", f"Erro mudando o baud: {e}")

    def _start_monitor(self):
        self.monitor = MonitorThread(self.port)
        self.monitor.line.connect(lambda s: self.log("app", s))
        self.monitor.failed.connect(self._port_failed)
        self.monitor.start()

    def _stop_monitor(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor = None

    def _port_failed(self, err):
        self.log("err", f"A porta caiu: {err}")
        self.monitor = None
        self.disconnect_port()
        self.refresh_ports()

    # ====================================================================================================
    # ---ENVIO DE COMANDOS---

    def send_command(self):
        if not self.port or self.worker:
            return
        text = self.ed_send.text()
        eol = self.cb_eol.currentData()
        if not text and not eol:
            return
        try:
            self.port.write((text + eol).encode("latin-1", errors="replace"))
        except Exception as e:
            self.log("err", f"Erro enviando: {e}")
            return
        shown = text + eol.replace("\r", "\\r").replace("\n", "\\n")
        self.log("tx", shown)
        self.ed_send.add(text)
        self.ed_send.clear()
        self.cfg["line_ending"] = eol

    # ====================================================================================================
    # ---ARQUIVO---

    def browse(self):
        start = os.path.dirname(self.ed_file.text()) if self.ed_file.text() else ""
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo .hex", start,
                                              "Intel HEX (*.hex);;Todos os arquivos (*)")
        if path:
            self.set_file(path)

    def set_file(self, path, quiet=False):
        self.ed_file.setText(path)
        self.ed_file.setToolTip(path)
        try:
            self.image = load_image(path)
        except (HexError, OSError) as e:
            self.image = None
            self.lb_info.setText("Arquivo inválido.")
            self.log("err", f"{os.path.basename(path)}: {e}")
            self._update_state()
            return
        self.cfg["last_file"] = path
        info = (f"{self.image.used_words} words de programa ({self.image.percent:.0f}% de {APP_END}), "
                f"{len(self.image.rows)} linhas, {len(self.image.eeprom)} bytes de EEPROM")
        self.lb_info.setText(info)
        if quiet:
            return self._update_state()
        self.log("info", f"Arquivo: {os.path.basename(path)} - {info}")
        for w in self.image.warnings:
            self.log("warn", f"AVISO: {w}")
        self._update_state()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls and not self.worker:
            self.set_file(urls[0].toLocalFile())

    # ====================================================================================================
    # ---GRAVACAO---

    def start_program(self):
        if not (self.port and self.image) or self.worker:
            return
        # recarrega o .hex (pode ter sido recompilado no MPLAB depois de selecionado)
        self.set_file(self.ed_file.text(), quiet=True)
        if not self.image:
            return
        self._stop_monitor()
        self.progress.setValue(0)
        self.worker = ProgramThread(self.port, self.image,
                                    boot_baud=int(self.cfg["bootloader_baud"]),
                                    wait_s=float(self.cfg["wait_reset_s"]),
                                    verify=self.ck_verify.isChecked(),
                                    dtr_reset=self.ck_dtr.isChecked())
        self.worker.log.connect(self.log)
        self.worker.progress.connect(lambda d, t: self.progress.setValue(int(100 * d / t)))
        self.worker.done.connect(self._program_done)
        self.worker.start()
        self.statusBar().showMessage("Gravando...")
        self._update_state()

    def cancel(self):
        if self.worker:
            self.worker.cancel()

    def _program_done(self, ok, elapsed):
        self.worker.wait()
        self.worker = None
        if ok:
            stamp = f"{elapsed:.1f} s às {datetime.now():%H:%M:%S} ({os.path.basename(self.ed_file.text())})"
            self.cfg["last_program"] = stamp
            self.progress.setValue(100)
            self.lb_last.setText(f"Última gravação: {stamp}")
        else:
            self.progress.setValue(0)
            last = self.cfg.get("last_program") or "-"
            self.lb_last.setText(f"Gravação falhou. Última gravação OK: {last}")
        if self.port:
            self._start_monitor()
        self._update_state()

    # ====================================================================================================
    # ---ESTADO DOS BOTOES---

    def _update_state(self):
        busy = self.worker is not None
        connected = self.port is not None
        self.cb_port.setEnabled(not connected)
        self.bt_refresh.setEnabled(not connected)
        self.cb_baud.setEnabled(not busy)
        self.bt_connect.setEnabled(not busy and (connected or bool(self.cb_port.currentData())))
        self.bt_connect.setText("Desconectar" if connected else "Conectar")
        self.bt_browse.setEnabled(not busy)
        self.ck_verify.setEnabled(not busy)
        self.ck_dtr.setEnabled(not busy)
        self.bt_program.setEnabled(connected and self.image is not None and not busy)
        self.ed_send.setEnabled(connected and not busy)
        self.cb_eol.setEnabled(not busy)
        self.bt_send.setEnabled(connected and not busy)
        self.bt_cancel.setEnabled(busy)
        if not busy:
            self.statusBar().showMessage(
                f"Conectado em {self.port.port} @ {self.cb_baud.currentData()} bps" if connected else "Desconectado")

    # ====================================================================================================
    # ---FECHAR---

    def closeEvent(self, e):
        if self.worker:
            self.worker.cancel()
            self.worker.wait(3000)
        self.disconnect_port()
        self.cfg["verify"] = self.ck_verify.isChecked()
        self.cfg["dtr_reset"] = self.ck_dtr.isChecked()
        helpers.save_settings(self.cfg)
        e.accept()
