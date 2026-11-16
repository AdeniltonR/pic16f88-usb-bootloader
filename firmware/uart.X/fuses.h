/*
 * NOME: Adenilton Ribeiro
 * DATA: 14/02/2025
 * PROJETO: fuses.h
 * VERSAO: 1.0.0
 * DESCRICAO: - feat: Configuracoes de bits do PIC16F88
 *            - docs:PIC16F88 - MPLAB X IDE v6.20 - Compilador XC8 2.50
 * LINKS: - 
*/

// ========================================================================================================
/**
 * @brief Fuses.h
 * 
 */ 
#ifndef FUSES_H
#define FUSES_H

// Configuracoes de Bits do PIC16F88

// Declaracoes de configuracao da linha fonte 'C'

// CONFIG1
#pragma config FOSC = HS        // Bits de selecao do oscilador (Oscilador EXTRC; funcao CLKO no pino RA6/OSC2/CLKO)
#pragma config WDTE = OFF       // Bit de habilitacao do Watchdog Timer (WDT habilitado)
#pragma config PWRTE = OFF      // Bit de habilitacao do Timer de Inicializacao (PWRT desabilitado)
#pragma config MCLRE = ON       // Bit de selecao da funcao do pino RA5/MCLR/VPP (Pino RA5/MCLR/VPP com funcao de MCLR)
#pragma config BOREN = OFF      // Bit de habilitacao do Reset por Queda de Tensao (BOR habilitado)
#pragma config LVP = OFF        // Bit de habilitacao da Gravacao em Baixa Voltagem (Pino RB3/PGM com funcao PGM, Gravacao em Baixa Voltagem habilitada)
#pragma config CPD = OFF        // Bit de protecao do codigo da memoria de dados EEPROM (Protecao de codigo desativada)
#pragma config WRT = OFF        // Bits de habilitacao de escrita na memoria Flash (Protecao contra escrita desativada)
#pragma config CCPMX = RB0      // Bit de selecao do pino CCP1 (Funcao CCP1 no pino RB0)
#pragma config CP = OFF         // Bit de protecao do codigo da memoria Flash (Protecao de codigo desativada)

// CONFIG2
#pragma config FCMEN = ON       // Bit de habilitacao do Monitor de Relogio a Prova de Falhas (Monitor de Relogio a Prova de Falhas habilitado)
#pragma config IESO = ON        // Bit de alternancia entre oscilador interno e externo (Modo de alternancia interna/externa habilitado)

// Declaracoes #pragma config devem preceder as inclusoes de arquivos do projeto.
// Use enums do projeto ao inves de #define para ON e OFF.

#include <xc.h>

#endif