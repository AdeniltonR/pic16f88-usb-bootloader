/*
 * NOME: Adenilton Ribeiro
 * DATA: 14/02/2025
 * PROJETO: UART.c
 * VERSAO: 1.0.1
 * DESCRICAO: - feat: Configuracao dinamica dos pinos RX e TX
 *            - feat: Enviar e receber dados pela serial
 *            - docs: PIC16F88 - MPLAB X IDE v6.20 - Compilador XC8 2.50
 */

// ========================================================================================================
//---BIBLIOTECAS---

#include "UART.h"

// ========================================================================================================
//---VARIAVEIS GLOBAIS---

volatile unsigned char *TRIS_RX;
volatile unsigned char *RX_PORT;
unsigned char RX_PIN;

volatile unsigned char *TRIS_TX;
volatile unsigned char *TX_PORT;
unsigned char TX_PIN;

// ========================================================================================================
/**
 * @brief Define os pinos RX e TX e ajusta dinamicamente o TRIS correto para cada PORT
 * 
 * @param tris_rx Ponteiro para o registrador TRIS do RX
 * @param rx_port Ponteiro para o registrador do PORT RX
 * @param rx_pin Numero do pino RX
 * @param tris_tx Ponteiro para o registrador TRIS do TX
 * @param tx_port Ponteiro para o registrador do PORT TX
 * @param tx_pin Numero do pino TX
 */
void UART_set_pins(volatile unsigned char *tris_rx, volatile unsigned char *rx_port, unsigned char rx_pin, 
    volatile unsigned char *tris_tx, volatile unsigned char *tx_port, unsigned char tx_pin) {
    TRIS_RX = tris_rx;
    RX_PORT = rx_port;
    RX_PIN = rx_pin;

    TRIS_TX = tris_tx;
    TX_PORT = tx_port;
    TX_PIN = tx_pin;

    //---configuracao dos pinos RX e TX no TRIS correto---
    *TRIS_RX |= (1 << RX_PIN);  // RX como entrada
    *TRIS_TX &= ~(1 << TX_PIN); // TX como saida
}

// ========================================================================================================
/**
 * @brief Inicializa a UART com uma taxa de baud personalizada utilizando apenas registradores
 * 
 * @note Configura os registradores diretamente para comunicacao UART
 * 
 * @param baud_rate Taxa de transmissao (ex: 9600)
 */
void UART_init_baud(const long int baud_rate) {
    uint16_t valor;
    //---calcula o valor do registrador de Baud Rate---
    valor = (unsigned char)((_XTAL_FREQ / (baud_rate * 16)) - 1);
    TXSTA |= (1 << 2);      // TXSTAbits.BRGH = 1 (Alta velocidade)

    //---se o valor for maior que 255, usa baixa velocidade---
    if (valor > (unsigned char)255) {
        valor = (unsigned char)((_XTAL_FREQ / (baud_rate * 64)) - 1);
        TXSTA &= ~(1 << 2); // TXSTAbits.BRGH = 0 (Baixa velocidade)
    }

    //---configuracao dos pinos RX e TX---
    *TRIS_RX |= (1 << 2);  // RB2 como entrada (RX)
    *TRIS_TX &= ~(1 << 5); // RB5 como saida (TX)

    //---configuracao da UART---
    TXSTA &= ~(1 << 4); // TXSTAbits.SYNC = 0 (Modo assincrono)
    TXSTA &= ~(1 << 6); // TXSTAbits.TX9 = 0 (8 bits de dados)

    SPBRG = (uint8_t)(valor & 0xFF);      // Configura a taxa de Baud Rate
    RCSTA |= (1 << 7);  // RCSTAbits.SPEN = 1 (Habilita a UART)
    TXSTA |= (1 << 5);  // TXSTAbits.TXEN = 1 (Habilita TX)
    RCSTA |= (1 << 4);  // RCSTAbits.CREN = 1 (Habilita RX)
}

// ========================================================================================================
/**
 * @brief Void UART read
 * 
 * @note Funcao para ler um caractere da UART
 * 
 * @return char 
 */
char UART_read(void) {
    if (PIR1 & (1 << RCIF)) {       // Verifica se ha dados disponiveis
        if (RCSTA & (1 << OERR)) {  // Verifica erro de estouro de buffer
            RCSTA &= ~(1 << CREN);
            __asm("NOP");
            RCSTA |= (1 << CREN);
        }
        return RCREG;               // Retorna caractere recebido
    }
    return 0;
}

// ========================================================================================================
/**
 * @brief Void UART write
 * 
 * @note Funcao para escrever um caractere na UART
 * 
 * @param dados 
 */
void UART_write(char dados) {
    //---coloca o caractere 'dados' no registrador de transmissao TXREG para envio---
    TXREG = dados;
    while (!(TXSTA & (1 << TRMT)));  // Aguarda buffer de transmissao esvaziar
}

// ========================================================================================================
/**
 * @brief Void UART printf
 * 
 * @note  Funcao para escrever uma string na UART
 * 
 * @param cadena 
 */
void UART_printf(char *cadena) {
    //---loop ate o caractere nulo (0x00) que marca o final da string---
    while(*cadena !=0x00){
        UART_write(*cadena); // Envia o caractere atual da string para a UART (porta serial)
        cadena++;            // Move o ponteiro para o proximo caractere na string
    }
}

// ========================================================================================================
/**
 * @brief Void UART putch
 * 
 * @note Funcao personalizada para uso com printf
 * 
 * @param dados 
 */
void putch(char dados) {
    UART_write(dados);
}
