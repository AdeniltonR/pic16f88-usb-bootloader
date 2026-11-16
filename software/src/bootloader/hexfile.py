"""
NOME: Adenilton Ribeiro
DATA: 14/11/2026
PROJETO: hexfile.py
VERSAO: 1.0.0
DESCRICAO: - feat: Leitura do Intel HEX do XC8 e montagem da imagem para o bootloader UART do PIC16F88
"""

# ========================================================================================================
# ---MAPA DE MEMORIA (precisa bater com bootloader.s)---

ROW_WORDS = 32                  # linha de apagamento do PIC16F88
BL_BASE = 0x0F00                # inicio do bootloader
BL_STUB = 0x0EE0                # linha do stub (inicio do app relocado)
APP_END = BL_STUB               # app pode usar 0x0000 .. 0x0EDF
FLASH_WORDS = 0x1000
BLANK = 0x3FFF

BL_CONFIG = {0x2007: 0x3F2A, 0x2008: 0x3FFF}    # config gravada junto com o bootloader
EE_BASE = 0x2100                # EEPROM de dados no .hex (endereco de word)

OP_CLRF_PCLATH = 0x018A
OP_BSF_PCLATH3 = 0x158A
OP_GOTO_BL = 0x2F00             # goto 0x700 (com PCLATH<3> = 1 -> 0x0F00)
OP_GOTO_MASK, OP_GOTO = 0x3800, 0x2800


class HexError(Exception):
    pass


# ========================================================================================================
# ---LEITURA DO .HEX---

def read_hex(path):
    """Le um Intel HEX do XC8. Retorna ({endereco_de_word: valor_14bits}, {endereco_eeprom: byte})."""
    data = {}
    base = 0
    with open(path, "r") as f:
        for num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if not line.startswith(":"):
                raise HexError(f"linha {num}: nao e Intel HEX")
            try:
                raw = bytes.fromhex(line[1:])
            except ValueError:
                raise HexError(f"linha {num}: caractere invalido")
            if len(raw) < 5 or len(raw) != raw[0] + 5:
                raise HexError(f"linha {num}: tamanho invalido")
            if (sum(raw) & 0xFF) != 0:
                raise HexError(f"linha {num}: checksum invalido")
            n, addr, typ = raw[0], (raw[1] << 8) | raw[2], raw[3]
            payload = raw[4:4 + n]
            if typ == 0x00:
                for i, b in enumerate(payload):
                    data[base + addr + i] = b
            elif typ == 0x01:
                break
            elif typ == 0x02:
                base = ((payload[0] << 8) | payload[1]) << 4
            elif typ == 0x04:
                base = ((payload[0] << 8) | payload[1]) << 16
            # tipos 03/05 (endereco de inicio) sao ignorados

    words, eeprom = {}, {}
    for baddr in sorted(data):
        waddr = baddr >> 1
        if waddr in words or (waddr - EE_BASE) in eeprom:
            continue
        lo = data.get(waddr << 1, 0xFF)
        hi = data.get((waddr << 1) | 1, 0xFF)
        if EE_BASE <= waddr < EE_BASE + 256:
            eeprom[waddr - EE_BASE] = lo
        else:
            words[waddr] = ((hi << 8) | lo) & 0x3FFF
    return words, eeprom


# ========================================================================================================
# ---PREPARACAO DA IMAGEM---

def is_goto(op):
    return (op & OP_GOTO_MASK) == OP_GOTO


class Image:
    """Imagem pronta para gravar: linhas da flash, stub e EEPROM."""

    def __init__(self, rows, stub, eeprom, used_words, warnings):
        self.rows = rows
        self.stub = stub
        self.eeprom = eeprom
        self.used_words = used_words
        self.warnings = warnings

    @property
    def percent(self):
        return 100.0 * self.used_words / APP_END


def build_image(words, eeprom=None):
    """Separa flash/config, valida o tamanho e reloca o vetor de reset."""
    warnings = []
    flash = {}
    for a, v in words.items():
        if a < FLASH_WORDS:
            flash[a] = v
        elif a in BL_CONFIG:
            if v != BL_CONFIG[a]:
                warnings.append(
                    f"config 0x{a:04X} do app = 0x{v:04X}, mas a gravada e 0x{BL_CONFIG[a]:04X} "
                    f"(a config vem do bootloader e nao e alterada).")
        elif 0x2000 <= a <= 0x2003:
            warnings.append(f"ID location 0x{a:04X} ignorada.")
        else:
            raise HexError(f"endereco 0x{a:04X} fora da memoria do PIC16F88")

    if not flash:
        raise HexError("o .hex nao tem codigo")

    over = sorted(a for a in flash if a >= APP_END and flash[a] != BLANK)
    if over:
        raise HexError(
            f"o app usa 0x{over[0]:04X}..0x{over[-1]:04X}, area reservada ao bootloader. "
            "No MPLAB X: Project Properties > XC8 Linker > Memory model > ROM ranges = default,-EE0-FFF")

    # ---vetor de reset do app (2 words, como o XC8 gera: [bcf/bsf PCLATH,3] + goto start)---
    w0, w1 = flash.get(0, BLANK), flash.get(1, BLANK)
    if not (is_goto(w1) or (is_goto(w0) and w1 == BLANK)):
        raise HexError(
            f"vetor de reset inesperado (0x{w0:04X} 0x{w1:04X}): era esperado um goto nas 2 primeiras words.")

    rows = {}
    for a, v in flash.items():
        if a >= APP_END:
            continue
        r = a & ~(ROW_WORDS - 1)
        rows.setdefault(r, [BLANK] * ROW_WORDS)[a - r] = v

    # ---linha 0: words 0..1 viram o salto do bootloader (o bootloader tambem garante isso)---
    rows.setdefault(0, [BLANK] * ROW_WORDS)
    rows[0][0] = OP_BSF_PCLATH3
    rows[0][1] = OP_GOTO_BL

    # ---stub: clrf PCLATH + as 2 words originais---
    stub = [BLANK] * ROW_WORDS
    stub[0:3] = [OP_CLRF_PCLATH, w0, w1]

    used = sum(1 for a in flash if a < APP_END)
    return Image(rows, stub, dict(eeprom or {}), used, warnings)


def load_image(path):
    """Atalho: le o .hex e monta a imagem."""
    words, eeprom = read_hex(path)
    return build_image(words, eeprom)
