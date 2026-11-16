;/*
; * NOME: Adenilton Ribeiro
; * DATA: 14/11/2026
; * PROJETO: bootloader.s
; * VERSAO: 1.0.1
; * DESCRICAO: - feat: Bootloader UART para PIC16F88 (gravacao via adaptador USB-serial)
; *            - refactor: fuses movidos para fuses.inc (Header Files)
; *            - docs: PIC16F88 - MPLAB X IDE v6.20 - pic-as (XC8 2.50) - cristal 16 MHz
; * LINKS: - DS30487D (PIC16F87/88), secao 3 (leitura/escrita da memoria flash)
; */

; ========================================================================================================
; ---MAPA DE MEMORIA---
;
;   0x0000-0x0001  salto para o bootloader (gravado pelo proprio bootloader na linha 0)
;   0x0002-0x0EDF  aplicacao (vetor de interrupcao 0x0004 continua sendo da aplicacao)
;   0x0EE0-0x0EFF  "stub": 2 primeiras words do app relocadas (gravado pelo uploader)
;   0x0F00-0x0FFF  bootloader (protegido contra escrita pelo proprio bootloader)
;
;   Na aplicacao (XC8): Project Properties > XC8 Linker > Memory model > ROM ranges = default,-EE0-FFF
;
; ---PROTOCOLO (UART 8N1, 19200 bps)---
;
;   Ao ligar, o bootloader espera ~1 s pelo byte 0x55. Se nao chegar, roda a aplicacao.
;
;   0x55                          -> 'K', VERSAO          (sincronismo)
;   'W' aH aL d0..d63 chk         -> 'K' / 'N' / 'P'      (grava linha de 32 words em aH:aL)
;   'R' aH aL                     -> d0..d63              (le 32 words a partir de aH:aL)
;   'D' a d chk                   -> 'K' / 'N'            (grava 1 byte na EEPROM de dados)
;   'E' a                         -> d                    (le 1 byte da EEPROM de dados)
;   'G'                           -> 'K'                  (roda a aplicacao)
;   outro                         -> '?'
;
;   Words em little-endian (byte baixo primeiro), como no .hex.
;   chk: soma de todos os bytes depois do comando (incluindo chk) = 0 (mod 256).
;   'N' = erro de checksum, 'P' = endereco protegido (>= 0x0F00).

; ========================================================================================================
; ---INCLUDE---

; fuses.inc (Header Files) tem que vir ANTES do xc.inc: o xc.inc define RB0 como macro
#include "fuses.inc"
#include <xc.inc>

; ========================================================================================================
; ---MAPEAMENTO DE ESTADO---

BL_VERSION  equ 0x10        ; versao 1.0
BL_BASE     equ 0x0F00      ; inicio do bootloader
BL_STUB     equ 0x0EE0      ; linha do stub (inicio da aplicacao relocado)
BL_SPBRG    equ 51          ; 16 MHz, BRGH=1 -> 19230 bps (erro 0,16%)
BL_TIMEOUT  equ 12          ; x ~82 ms = ~1 s esperando o sincronismo
BL_JUNK     equ 16          ; bytes errados aceitos antes de desistir e rodar o app
BL_SYNC     equ 0x55

; ========================================================================================================
; ---REGISTRADORES (enderecos ja mascarados com 0x7F; o banco e selecionado manualmente)---

R_INDF      equ 0x00
R_STATUS    equ 0x03
R_FSR       equ 0x04
R_PCLATH    equ 0x0A
R_PIR1      equ 0x0C        ; banco 0
R_RCSTA     equ 0x18        ; banco 0
R_TXREG     equ 0x19        ; banco 0
R_RCREG     equ 0x1A        ; banco 0
R_OPTION    equ 0x01        ; banco 1 (0x81)
R_TRISB     equ 0x06        ; banco 1 (0x86)
R_OSCCON    equ 0x0F        ; banco 1 (0x8F)
R_TXSTA     equ 0x18        ; banco 1 (0x98)
R_SPBRG     equ 0x19        ; banco 1 (0x99)
R_EEDATA    equ 0x0C        ; banco 2 (0x10C)
R_EEADR     equ 0x0D        ; banco 2 (0x10D)
R_EEDATH    equ 0x0E        ; banco 2 (0x10E)
R_EEADRH    equ 0x0F        ; banco 2 (0x10F)
R_EECON1    equ 0x0C        ; banco 3 (0x18C)
R_EECON2    equ 0x0D        ; banco 3 (0x18D)

; bits
B_C         equ 0           ; STATUS
B_Z         equ 2
B_RP0       equ 5
B_RP1       equ 6
B_TXIF      equ 4           ; PIR1
B_RCIF      equ 5
B_OERR      equ 1           ; RCSTA
B_CREN      equ 4
B_TRMT      equ 1           ; TXSTA
B_OSTS      equ 3           ; OSCCON
B_RD        equ 0           ; EECON1
B_WR        equ 1
B_WREN      equ 2
B_FREE      equ 4
B_EEPGD     equ 7

; ========================================================================================================
; ---VARIAVEIS (RAM comum 0x70-0x7F, acessivel em qualquer banco)---

v_cnt0      equ 0x70
v_cnt1      equ 0x71
v_cnt2      equ 0x72
v_chk       equ 0x73
v_addrh     equ 0x74
v_addrl     equ 0x75
v_tmp       equ 0x76
v_dat       equ 0x77
v_cnt       equ 0x78
v_junk      equ 0x79

BUF         equ 0x20        ; buffer de 64 bytes no banco 0 (0x20-0x5F), acessado via FSR

; ========================================================================================================
; ---VETOR DE RESET---

PSECT blCode,class=CODE,delta=2,abs
ORG 0x0000
    bsf     R_PCLATH, 3         ; pagina 1
    goto    bl_entry            ; 0x0F00

; ========================================================================================================
; ---BOOTLOADER---

ORG BL_BASE

bl_entry:
    clrf    R_STATUS            ; banco 0, IRP = 0
    movlw   0x08                ; PCLATH = pagina 1 (0x0800-0x0FFF)
    movwf   R_PCLATH

    ;---espera o cristal assumir (two-speed start-up)---
    bsf     R_STATUS, B_RP0     ; banco 1
bl_osts:
    btfss   R_OSCCON, B_OSTS
    goto    bl_osts

    ;---UART 19200 8N1: RB2 = RX, RB5 = TX---
    movlw   BL_SPBRG
    movwf   R_SPBRG
    movlw   0x24                ; TXEN = 1, BRGH = 1, SYNC = 0
    movwf   R_TXSTA
    bsf     R_TRISB, 2          ; RB2 entrada
    bcf     R_OPTION, 7         ; RBPU = 0: pull-ups do PORTB (RX nao flutua sem o adaptador)
    bcf     R_TRISB, 5          ; RB5 saida
    bcf     R_STATUS, B_RP0     ; banco 0
    movlw   0x90                ; SPEN = 1, CREN = 1
    movwf   R_RCSTA

    ;---espera o sincronismo---
    movlw   BL_JUNK
    movwf   v_junk
bl_wait_sync:
    call    getc_timeout
    btfsc   R_STATUS, B_C
    goto    run_app             ; timeout -> aplicacao
    xorlw   BL_SYNC
    btfsc   R_STATUS, B_Z
    goto    do_sync
    decfsz  v_junk, f
    goto    bl_wait_sync
    goto    run_app             ; muito lixo na serial -> aplicacao

; ========================================================================================================
; ---LOOP DE COMANDOS---

do_sync:
    movlw   'K'
    call    putc
    movlw   BL_VERSION
    call    putc

cmd_loop:
    call    getc
    xorlw   BL_SYNC
    btfsc   R_STATUS, B_Z
    goto    do_sync
    xorlw   BL_SYNC ^ 'W'
    btfsc   R_STATUS, B_Z
    goto    cmd_write
    xorlw   'W' ^ 'R'
    btfsc   R_STATUS, B_Z
    goto    cmd_read
    xorlw   'R' ^ 'D'
    btfsc   R_STATUS, B_Z
    goto    cmd_ee_write
    xorlw   'D' ^ 'E'
    btfsc   R_STATUS, B_Z
    goto    cmd_ee_read
    xorlw   'E' ^ 'G'
    btfsc   R_STATUS, B_Z
    goto    cmd_go
    movlw   '?'
    goto    reply

reply_nak:
    movlw   'N'
    goto    reply
reply_prot:
    movlw   'P'
    goto    reply
reply_ack:
    movlw   'K'
reply:
    call    putc
    goto    cmd_loop

; ========================================================================================================
; ---'W' aH aL d0..d63 chk : grava uma linha de 32 words---

cmd_write:
    clrf    v_chk
    call    getc_chk
    movwf   v_addrh
    call    getc_chk
    movwf   v_addrl
    movlw   BUF
    movwf   R_FSR
    movlw   64
    movwf   v_cnt
cw_rx:
    call    getc_chk
    movwf   R_INDF
    incf    R_FSR, f
    decfsz  v_cnt, f
    goto    cw_rx
    call    getc_chk            ; checksum
    movf    v_chk, f
    btfss   R_STATUS, B_Z
    goto    reply_nak

    ;---protege o bootloader: so aceita linhas < 0x0F00---
    movlw   0x0F
    subwf   v_addrh, w          ; C = 1 se aH >= 0x0F
    btfsc   R_STATUS, B_C
    goto    reply_prot
    movlw   0xE0
    andwf   v_addrl, f          ; alinha na linha de 32 words

    ;---linha 0: forca o salto para o bootloader nas words 0 e 1---
    movf    v_addrh, w
    iorwf   v_addrl, w
    btfss   R_STATUS, B_Z
    goto    cw_flash
    movlw   0x8A                ; 0x158A = bsf PCLATH,3
    movwf   BUF+0
    movlw   0x15
    movwf   BUF+1
    clrf    BUF+2               ; 0x2F00 = goto 0x700 (com PCLATH<3> -> 0x0F00)
    movlw   0x2F
    movwf   BUF+3

cw_flash:
    ;---apaga a linha (32 words)---
    call    set_addr            ; -> banco 2
    bsf     R_STATUS, B_RP0     ; banco 3
    movlw   0x94                ; EEPGD = 1, FREE = 1, WREN = 1
    movwf   R_EECON1
    call    ee_unlock
    clrf    R_EECON1

    ;---grava as 32 words (o PIC grava em blocos de 4, ao escrever a word com EEADR<1:0> = 11)---
    movlw   BUF
    movwf   R_FSR
    movlw   32
    movwf   v_cnt
cw_word:
    call    set_addr            ; -> banco 2
    movf    R_INDF, w
    movwf   R_EEDATA
    incf    R_FSR, f
    movf    R_INDF, w
    movwf   R_EEDATH
    incf    R_FSR, f
    bsf     R_STATUS, B_RP0     ; banco 3
    movlw   0x84                ; EEPGD = 1, WREN = 1
    movwf   R_EECON1
    call    ee_unlock
    clrf    R_EECON1
    bcf     R_STATUS, B_RP0
    bcf     R_STATUS, B_RP1     ; banco 0
    incf    v_addrl, f
    decfsz  v_cnt, f
    goto    cw_word
    goto    reply_ack

; ========================================================================================================
; ---'R' aH aL : le 32 words---

cmd_read:
    call    getc
    movwf   v_addrh
    call    getc
    movwf   v_addrl
    movlw   32
    movwf   v_cnt
cr_word:
    call    set_addr            ; -> banco 2
    bsf     R_STATUS, B_RP0     ; banco 3
    bsf     R_EECON1, B_EEPGD
    bsf     R_EECON1, B_RD
    nop                         ; 2 instrucoes ignoradas apos RD (flash)
    nop
    bcf     R_STATUS, B_RP0     ; banco 2
    movf    R_EEDATA, w
    movwf   v_tmp
    movf    R_EEDATH, w
    movwf   v_dat
    bcf     R_STATUS, B_RP1     ; banco 0
    movf    v_tmp, w
    call    putc
    movf    v_dat, w
    call    putc
    incf    v_addrl, f
    btfsc   R_STATUS, B_Z
    incf    v_addrh, f
    decfsz  v_cnt, f
    goto    cr_word
    goto    cmd_loop

; ========================================================================================================
; ---'D' a d chk : grava 1 byte na EEPROM de dados---

cmd_ee_write:
    clrf    v_chk
    call    getc_chk
    movwf   v_addrl
    call    getc_chk
    movwf   v_dat
    call    getc_chk            ; checksum
    movf    v_chk, f
    btfss   R_STATUS, B_Z
    goto    reply_nak
    bsf     R_STATUS, B_RP1     ; banco 2
    movf    v_addrl, w
    movwf   R_EEADR
    movf    v_dat, w
    movwf   R_EEDATA
    bsf     R_STATUS, B_RP0     ; banco 3
    movlw   0x04                ; EEPGD = 0, WREN = 1
    movwf   R_EECON1
    call    ee_unlock
cee_wait:
    btfsc   R_EECON1, B_WR      ; ~4 ms
    goto    cee_wait
    clrf    R_EECON1
    bcf     R_STATUS, B_RP0
    bcf     R_STATUS, B_RP1     ; banco 0
    goto    reply_ack

; ========================================================================================================
; ---'E' a : le 1 byte da EEPROM de dados---

cmd_ee_read:
    call    getc
    bsf     R_STATUS, B_RP1     ; banco 2
    movwf   R_EEADR
    bsf     R_STATUS, B_RP0     ; banco 3
    clrf    R_EECON1            ; EEPGD = 0
    bsf     R_EECON1, B_RD
    bcf     R_STATUS, B_RP0     ; banco 2
    movf    R_EEDATA, w
    bcf     R_STATUS, B_RP1     ; banco 0
    goto    reply

; ========================================================================================================
; ---'G' : roda a aplicacao---

cmd_go:
    movlw   'K'
    call    putc

run_app:
    ;---espera o ultimo byte sair pela serial---
    btfss   R_PIR1, B_TXIF
    goto    run_app
    bsf     R_STATUS, B_RP0     ; banco 1
    nop
ra_trmt:
    btfss   R_TXSTA, B_TRMT
    goto    ra_trmt

    ;---devolve os perifericos ao estado de reset---
    movlw   0x02
    movwf   R_TXSTA
    clrf    R_SPBRG
    movlw   0xFF
    movwf   R_TRISB
    movwf   R_OPTION
    bcf     R_STATUS, B_RP0     ; banco 0
    clrf    R_RCSTA
    clrf    R_STATUS            ; banco 0, IRP = 0

    ;---salta para o stub (PCLATH<3> = 1 -> 0x0EE0)---
    ;   O stub faz "clrf PCLATH" e executa as 2 primeiras words originais do app.
    ;   Se nao houver app (stub apagado = 0x3FFF), a execucao percorre a linha
    ;   apagada e cai de novo em 0x0F00 (bootloader).
    goto    BL_STUB & 0x7FF     ; 0x0EE0 (campo de 11 bits + PCLATH<3>)

; ========================================================================================================
; ---ROTINAS---

;---EEADRH:EEADR = v_addrh:v_addrl. Sai no banco 2.---
set_addr:
    bcf     R_STATUS, B_RP0
    bsf     R_STATUS, B_RP1     ; banco 2
    movf    v_addrh, w
    movwf   R_EEADRH
    movf    v_addrl, w
    movwf   R_EEADR
    return

;---sequencia obrigatoria 55h/AAh + WR. Chamar no banco 3 com EECON1 ja configurado.---
ee_unlock:
    movlw   0x55
    movwf   R_EECON2
    movlw   0xAA
    movwf   R_EECON2
    bsf     R_EECON1, B_WR
    nop                         ; 2 instrucoes ignoradas apos WR (flash)
    nop
    return

;---envia W pela UART (banco 0)---
putc:
    btfss   R_PIR1, B_TXIF
    goto    putc
    movwf   R_TXREG
    return

;---recebe um byte em W, somando em v_chk (banco 0)---
getc_chk:
    call    getc
    addwf   v_chk, f
    return

;---recebe um byte em W, bloqueante (banco 0)---
getc:
    btfsc   R_RCSTA, B_OERR
    goto    getc_oerr
    btfss   R_PIR1, B_RCIF
    goto    getc
    movf    R_RCREG, w
    return
getc_oerr:
    bcf     R_RCSTA, B_CREN     ; limpa overrun
    bsf     R_RCSTA, B_CREN
    goto    getc

;---recebe um byte com timeout de ~1 s. C = 0: byte em W. C = 1: timeout (banco 0)---
getc_timeout:
    movlw   BL_TIMEOUT
    movwf   v_cnt2
    clrf    v_cnt1
    clrf    v_cnt0
gto_loop:
    btfsc   R_PIR1, B_RCIF      ; 5 ciclos por volta: 5 x 65536 x 0,25 us = ~82 ms
    goto    gto_byte
    decfsz  v_cnt0, f
    goto    gto_loop
    decfsz  v_cnt1, f
    goto    gto_loop
    decfsz  v_cnt2, f
    goto    gto_loop
    bsf     R_STATUS, B_C
    return
gto_byte:
    call    getc
    bcf     R_STATUS, B_C
    return

bl_end:

    END
