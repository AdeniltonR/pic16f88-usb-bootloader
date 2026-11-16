;/*
; * NOME: Adenilton Ribeiro
; * DATA: 15/11/2026
; * PROJETO: fuses.inc
; * VERSAO: 1.0.0
; * DESCRICAO: - feat: Bits de configuracao (fuses) do PIC16F88 para o bootloader UART
; *            - docs: PIC16F88 - MPLAB X IDE v6.20 - pic-as (XC8 2.50) - cristal 16 MHz
; * LINKS: - DS30487D (PIC16F87/88), secao 15.1 (Configuration Bits)
; */

; ========================================================================================================
; ---OBSERVACOES---
;
;   - Estes fuses valem para o bootloader E para a aplicacao: o bootloader nao regrava a
;     configuracao, entao o #pragma config dos apps em C e ignorado.
;   - Arquivo em sintaxe pic-as (diretiva CONFIG), nao em C (#pragma config).
;   - Deve ser incluido ANTES do #include <xc.inc>: o xc.inc define macros como RB0 (bit do
;     PORTB), que o pre-processador trocaria dentro de "CCPMX = RB0".

; ========================================================================================================
; ---CONFIGURACAO---

CONFIG FOSC = HS        ; Cristal 16 MHz
CONFIG WDTE = OFF       ; Watchdog desligado
CONFIG PWRTE = OFF      ; Power-up timer desligado
CONFIG MCLRE = ON       ; RA5 = MCLR
CONFIG BOREN = OFF      ; Brown-out desligado
CONFIG LVP = OFF        ; Gravacao em baixa tensao desligada
CONFIG CPD = OFF        ; Sem protecao da EEPROM
CONFIG WRT = OFF        ; OBRIGATORIO: sem protecao de escrita (o bootloader escreve na flash)
CONFIG CCPMX = RB0      ; CCP1 em RB0
CONFIG CP = OFF         ; Sem protecao de codigo
CONFIG FCMEN = ON       ; Monitor de clock
CONFIG IESO = ON        ; Two-speed start-up
