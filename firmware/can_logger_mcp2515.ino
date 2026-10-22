/*
 * ============================================================================
 * PROJETO: DAF CF CAN Logger (J1939 / OBD-II)
 * HARDWARE: Arduino Uno / Nano + MCP2515 (Cristal 8 MHz)
 * ============================================================================
 * 
 * LIGAÇÕES (Arduino Uno / Nano <-> MCP2515):
 *   VCC  -> 5V (ou 3.3V dependendo do seu módulo MCP2515, a maioria azul é 5V)
 *   GND  -> GND
 *   CS   -> Pino Digital 10 (D10)
 *   SO   -> Pino Digital 12 (MISO / D12)
 *   SI   -> Pino Digital 11 (MOSI / D11)
 *   SCK  -> Pino Digital 13 (SCK / D13)
 *   INT  -> Pino Digital 2  (D2 - Interrupção)
 *
 * CONEXÃO AO VEÍCULO (DAF CF):
 *   CAN-H -> Conector FMS / V-CAN / OBD2 Pino 6
 *   CAN-L -> Conector FMS / V-CAN / OBD2 Pino 14
 *   GND   -> Chassi / Pino 4 ou 5 da OBD2 (muito importante para referência)
 *
 * BIBLIOTECA NECESSÁRIA NO ARDUINO IDE:
 *   Instale a biblioteca "mcp_can" (por Cory Fowler) através do Library Manager
 *   ou https://github.com/coryjfowler/MCP_CAN_lib
 * ============================================================================
 */

#include <SPI.h>
#include <mcp_can.h>

// Definições de Hardware
const int CAN0_CS = 10;     // Chip Select do MCP2515
const int CAN0_INT = 2;     // Pino de Interrupção

MCP_CAN CAN0(CAN0_CS);      // Instância da biblioteca

// Configurações da CAN
// Cristal: MCP_8MHZ (conforme selecionado)
// Velocidade: CAN_250KBPS (padrão J1939 em caminhões DAF)
// Dica: Se for Euro 6 OBD2 ou 500kbps, altere para CAN_500KBPS
#define CAN_CLOCK MCP_8MHZ
#define CAN_SPEED CAN_250KBPS

// Flag de controle de interrupção
volatile bool messageReceived = false;

void canInterrupt() {
  messageReceived = true;
}

void setup() {
  // Inicializa porta Serial em alta velocidade para não engargalar o log
  Serial.begin(115200);
  while (!Serial) {
    ; // Aguarda porta serial conectar (se Leonardo/Micro)
  }

  Serial.println(F("# DAF CF CAN Logger Iniciado"));
  Serial.println(F("# Config: Cristal 8MHz | Baud 250kbps"));

  // Inicializa o MCP2515
  // CAN0.begin(MODO_CAN, VELOCIDADE, CLOCK)
  // MODO_CAN: MCP_ANY (aceita qualquer mensagem sem filtros de hardware)
  if (CAN0.begin(MCP_ANY, CAN_SPEED, CAN_CLOCK) == CAN_OK) {
    Serial.println(F("# MCP2515 Inicializado com Sucesso!"));
  } else {
    Serial.println(F("# ERRO: Falha ao inicializar MCP2515. Verifique as conexoes e alimentacao."));
    while (1) {
      delay(1000);
    }
  }

  // Define modo de operação:
  // MCP_LISTENONLY: MODO ESCUTA - Não envia confirmação (ACK) nem perturba o barramento.
  //                 Altamente recomendado para caminhões DAF para evitar erros no painel!
  // MCP_NORMAL: Modo normal (envia ACK, necessário se for enviar comandos OBD2 request).
  CAN0.setMode(MCP_LISTENONLY);
  Serial.println(F("# Modo: LISTEN_ONLY (Seguro para rede do caminhao)"));

  // Configura interrupção no pino D2 (borda de descida / LOW)
  pinMode(CAN0_INT, INPUT);
  attachInterrupt(digitalPinToInterrupt(CAN0_INT), canInterrupt, FALLING);

  Serial.println(F("# Aguardando pacotes CAN..."));
  Serial.println(F("# PROTOCOL_READY"));
}

void loop() {
  // Verifica se houve interrupção ou lê o pino diretamente
  if (!digitalRead(CAN0_INT) || messageReceived) {
    messageReceived = false;

    long unsigned int rxId;
    unsigned char len = 0;
    unsigned char rxBuf[8];

    // Lê a mensagem do buffer do MCP2515
    if (CAN0.readMsgBuf(&rxId, &len, rxBuf) == CAN_OK) {
      unsigned long timestamp = millis();

      // Verifica se é extended (29-bit, padrão J1939) ou standard (11-bit)
      bool isExtended = (rxId & 0x80000000) == 0x80000000;
      rxId = rxId & 0x1FFFFFFF; // Remove flag de extended

      // Formato de saída compacta para o Python:
      // CAN:<timestamp>,<ext:1|0>,<id_hex>,<len>,<b0>,<b1>,...,<bN>
      Serial.print(F("CAN:"));
      Serial.print(timestamp);
      Serial.print(',');
      Serial.print(isExtended ? '1' : '0');
      Serial.print(',');
      
      // Imprime ID em Hexadecimal
      if (rxId < 0x10) Serial.print('0');
      Serial.print(rxId, HEX);
      Serial.print(',');
      Serial.print(len);

      // Imprime bytes de dados
      for (byte i = 0; i < len; i++) {
        Serial.print(',');
        if (rxBuf[i] < 0x10) Serial.print('0');
        Serial.print(rxBuf[i], HEX);
      }
      Serial.println();
    }
  }

  // Permite comandos simples via Serial do PC se necessário (ex: mudar velocidade)
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == 'N') {
      // Alterna para modo normal
      CAN0.setMode(MCP_NORMAL);
      Serial.println(F("# Modo alterado para: NORMAL"));
    } else if (cmd == 'L') {
      // Alterna para modo listen only
      CAN0.setMode(MCP_LISTENONLY);
      Serial.println(F("# Modo alterado para: LISTEN_ONLY"));
    }
  }
}
