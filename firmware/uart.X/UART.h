/*
 * NOME: Adenilton Ribeiro
 * DATA: 14/02/2025
 * PROJETO: UART.h
 * VERSAO: 1.0.1
 * DESCRICAO: - feat: Configuracao dinamica dos pinos RX e TX
 *            - feat: Enviar e receber dados pela serial
 *            - docs: PIC16F88 - MPLAB X IDE v6.20 - Compilador XC8 2.50
 */

// ========================================================================================================
/**
 * @brief UART.h
 * 
 */
#ifndef  UART
#define UART

// ========================================================================================================
// ---FREQUENCIA DO OSCILADOR---

#define _XTAL_FREQ 16000000

// ========================================================================================================
// ---BIBLIOTECA---

#include <xc.h>
#include <stdio.h>
#include <string.h>

// ========================================================================================================
//---MACROS---

#define __ms(t) __delay_ms(t)
#define __us(t) __delay_us(t)

// ========================================================================================================
//---CONSTANTS---

// ========================================================================================================
//---PROTOTIPO DA FUNCAO---

void UART_set_pins(volatile unsigned char *tris_rx, volatile unsigned char *rx_port, unsigned char rx_pin, 
    volatile unsigned char *tris_tx, volatile unsigned char *tx_port, unsigned char tx_pin);
void UART_init_baud(const long int baud_rate);
char UART_read(void);
void UART_write(char dados);
void UART_printf(char *cadena);
void putch(char dados);

#endif //UART