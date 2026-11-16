/*
 * NOME: Adenilton Ribeiro
 * DATA: 15/11/2026
 * PROJETO: UART
 * VERSAO: 1.2.1
 * DESCRICAO: - feat: Comunicacao serial com PIC.
 *            - refactor: removido o contador (o PIC so responde aos comandos)
 *            - feat: Comandos pela serial: 'a' liga o LED (RB0), 'b' desliga. Recebidos pela interrupcao de RX
 *            - docs: PIC16F88 - MPLAB X IDE v6.20 - Compilador XC8 2.50
 *            - docs: Gravar pelo bootloader: ROM ranges = default,-EE0-FFF (ver firmware/README.md)
 * LINKS: -
*/

// ========================================================================================================
// ---INCLUDE---

#include <xc.h>
#include <stdio.h>
#include <string.h>
#include "fuses.h"
#include "UART.h"

//---defina a frequencia do oscilador---
#define _XTAL_FREQ 16000000

// ========================================================================================================
//---MAPEAMENTO DE ESTADO---

/** @brief Velocidade do baud rate*/
#define BAUD_RATE 9600

// ========================================================================================================
//---MAPEAMENTO DE HARDWARE---

#define PIN_rx 2  // RB2
#define PIN_tx 5  // RB5
#define PIN_led (1<<0) // RB0

// ========================================================================================================
//---VARIAVEIS GLOBAIS---

/** @brief Ultimo comando recebido pela ISR ('a' ou 'b'); 0 = nenhum pendente*/
volatile char comando = 0;

// ========================================================================================================
//---PROTOTIPO DA FUNCAO---

void rx_interrupt_init(void);
void trata_comando(void);

// ========================================================================================================
/**
 * @brief Interrupcao (vetor 0x0004)
 *
 * @note RX da UART: 'a' liga o LED, 'b' desliga. O LED muda na hora; a resposta e enviada pelo main.
 *       Outros caracteres (ex.: \r e \n do fim de linha) sao ignorados.
 */
void __interrupt() isr(void) {
    if (PIR1bits.RCIF) {
        if (RCSTAbits.OERR) {           // Overrun: reinicia a recepcao
            RCSTAbits.CREN = 0;
            RCSTAbits.CREN = 1;
        }
        char c = RCREG;                 // Ler RCREG limpa o RCIF
        if (c == 'a' || c == 'A') {
            PORTB |= PIN_led;           // Liga o LED
            comando = 'a';
        } else if (c == 'b' || c == 'B') {
            PORTB &= ~PIN_led;          // Desliga o LED
            comando = 'b';
        }
    }
}

// ========================================================================================================
/**
 * @brief Void main
 *
 */
void main() {
    //---LED---
    TRISB &= ~PIN_led;  // RB0 como saida
    PORTB &= ~PIN_led;  // LED apagado

    //---configura os pinos da UART usando diferentes PORTs---
    UART_set_pins(&TRISB, &PORTB, PIN_rx,  // RX em PORTB
        &TRISB, &PORTB, PIN_tx);           // TX em PORTB

    //---inicializa UART---
    UART_init_baud(BAUD_RATE);

    //---interrupcao de RX---
    rx_interrupt_init();

    printf("UART Serial com Pic\n\r");
    printf("Comandos: 'a' liga o LED, 'b' desliga o LED\n\r");

    while(1) {
        //---responde aos comandos recebidos pela ISR---
        trata_comando();
        __ms(10);
    }
}

// ========================================================================================================
/**
 * @brief Habilita a interrupcao de recepcao da UART
 *
 */
void rx_interrupt_init(void) {
    PIE1bits.RCIE = 1;         // Habilita interrupcao de RX
    INTCONbits.PEIE = 1;        // Habilita interrupcoes de perifericos
    INTCONbits.GIE = 1;         // Habilita interrupcoes globais
}

// ========================================================================================================
/**
 * @brief Responde pela serial o comando recebido na ISR
 *
 */
void trata_comando(void) {
    char c;
    INTCONbits.GIE = 0;         // Le e limpa o comando sem ser interrompido no meio
    c = comando;
    comando = 0;
    INTCONbits.GIE = 1;

    if (c == 'a') {
        printf("LED ligado\n\r");
    } else if (c == 'b') {
        printf("LED desligado\n\r");
    }
}
