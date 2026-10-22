# DAF CF - CAN Bus (J1939 / OBD-II) Logger & Decoder

Sistema completo para captura, decodificação em tempo real e armazenamento de telemetria CAN (SAE J1939 e OBD-II) de caminhões **DAF CF**, utilizando **Arduino Uno / Nano + MCP2515 (Cristal 8 MHz)**.

---

## 📁 Estrutura do Projeto

```text
can_arduino_mcp/
├── dbc/                          # Pasta onde você coloca seus arquivos .dbc
│   ├── sample_j1939_daf.dbc      # DBC padrão J1939 de exemplo (RPM, Velocidade, Temp, etc.)
│   └── README.txt
├── firmware/                     # Código para gravar no Arduino
│   └── can_logger_mcp2515.ino    # Sketch Arduino com MCP2515 em modo Listen-Only
├── logs/                         # Pasta onde os logs são salvos automaticamente
│   ├── raw_can_*.csv             # Frames brutos com análise de J1939 (PGN, SA, Priority)
│   ├── decoded_can_*.csv         # Sinais físicos decodificados (RPM, km/h, °C, etc.)
│   └── can_log_*.asc             # Log no formato Vector CANoe/SavvyCAN
├── python/                       # Scripts de captura e decodificação no PC
│   ├── can_logger.py             # Logger em tempo real via USB Serial
│   ├── replay_and_export.py      # Re-decodificador offline de logs brutos
│   ├── simulate_truck_can.py     # Gerador de tráfego J1939 simulado para testes
│   └── requirements.txt          # Dependências Python (cantools, pyserial, colorama)
└── README.md
```

---

## 🔌 1. Esquema de Ligação do Hardware

### Arduino Uno / Nano  <--->  Módulo MCP2515 (Cristal 8 MHz)

| Pino do MCP2515 | Pino Arduino Uno / Nano | Descrição |
| :--- | :--- | :--- |
| **VCC** | **5V** (ou 3.3V) | Alimentação do módulo |
| **GND** | **GND** | Terra em comum |
| **CS** | **D10** | Chip Select SPI |
| **SO (MISO)** | **D12** | SPI MISO |
| **SI (MOSI)** | **D11** | SPI MOSI |
| **SCK** | **D13** | SPI Clock |
| **INT** | **D2** | Interrupção externa de recepção |

> ⚠️ **Atenção ao Resistor Terminal de 120 Ω:** O módulo MCP2515 possui um jumper (geralmente marcado como **J1**). Quando você se conectar a uma rede CAN existente do caminhão (que já possui terminação), **remova o jumper de 120 Ω** para não sobrecarregar o barramento.

---

## 🚚 2. Conexão no Caminhão DAF CF

Você pode conectar em dois pontos principais:

### Opção A: Conector de Diagnóstico OBD-II (Cabine)
* **Pino 6:** CAN High (CAN-H)
* **Pino 14:** CAN Low (CAN-L)
* **Pino 4 ou 5:** Chassi Ground (GND de referência - **muito importante ligar ao GND do Arduino**)

### Opção B: Conector FMS / Rede V-CAN (J1939)
* Conectores de telemetria FMS padrão da DAF (localizados atrás do tacógrafo ou na central elétrica).
* Velocidade de operação: **250 kbps** (padrão J1939).

---

## 🛠️ 3. Gravando o Firmware no Arduino

1. Abra a **Arduino IDE**.
2. Vá em **Sketch -> Incluir Biblioteca -> Gerenciar Bibliotecas...** (ou `Ctrl + Shift + I`).
3. Procure por **`mcp_can`** pelo autor **Cory Fowler** e clique em **Instalar**.
4. Abra o arquivo [firmware/can_logger_mcp2515.ino](file:///c:/Users/vdh91/OneDrive/Área de Trabalho/can_arduino_mcp/firmware/can_logger_mcp2515.ino).
5. Selecione sua placa (**Arduino Uno** ou **Nano**) e a **Porta COM**.
6. Clique em **Carregar (Upload)**.

> 🔒 **Modo Listen-Only:** O firmware está configurado por padrão em `MCP_LISTENONLY`. Nesse modo, o Arduino apenas escuta o tráfego do caminhão sem emitir bits dominantes ou ACKs, garantindo **segurança total** sem risco de acender luzes de falha no painel do caminhão.

---

## 💻 4. Executando o Logger no PC

### Passo 1: Instale as bibliotecas necessárias
No terminal do seu computador (PowerShell ou Prompt de Comando), execute:
```bash
pip install -r python/requirements.txt
```

### Passo 2: Adicione seus arquivos `.dbc`
Copie os seus arquivos `.dbc` (ex: `daf_cf.dbc`, `j1939.dbc`, `obd2.dbc`) para a pasta:
📁 `can_arduino_mcp/dbc/`

*(O logger carrega automaticamente todos os arquivos `.dbc` presentes nessa pasta e une seus sinais).*

### Passo 3: Inicie a gravação
Com o Arduino conectado na USB, execute:
```bash
python python/can_logger.py
```

O script detectará a porta COM automaticamente, carregará os arquivos DBC e começará a gravar os logs em tempo real na pasta `logs/`.

Para parar a gravação a qualquer momento e salvar com segurança, pressione **`Ctrl + C`**.

---

## 📊 5. Formatos de Log Gerados

Para cada sessão de gravação, são criados 3 arquivos na pasta `logs/`:

1. **`raw_can_YYYYMMDD_HHMMSS.csv`**:
   - Contém todos os frames brutos com timestamp, ID hexadecimal, dados em hex, e o cálculo de J1939 (PGN, Source Address, Prioridade).
2. **`decoded_can_YYYYMMDD_HHMMSS.csv`**:
   - Contém todos os sinais físicos decodificados pelos seus arquivos DBC (ex: Rotação do Motor em RPM, Velocidade do Veículo em km/h, Temperatura da Água em °C, etc.).
3. **`can_log_YYYYMMDD_HHMMSS.asc`**:
   - Arquivo padrão Vector ASCII (compatível com softwares profissionais automotivos como Vector CANoe, CANalyzer e SavvyCAN).

---

## 🔄 6. Re-decodificação Offline (`replay_and_export.py`)

Se você gravou um log na estrada e depois recebeu um novo arquivo `.dbc` da DAF, você **não precisa gravar tudo de novo**.

Basta executar o utilitário de reprocessamento:
```bash
python python/replay_and_export.py --raw logs/raw_can_20261022_120000.csv
```
Ele lerá o arquivo bruto e gerará um novo CSV com todos os novos sinais decodificados pelo novo DBC!
