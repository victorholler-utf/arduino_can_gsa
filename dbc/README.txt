# Diretório de Arquivos DBC

Coloque aqui os seus arquivos `.dbc` de J1939 e OBD-II do caminhão DAF CF.

Exemplos de arquivos suportados:
- `daf_j1939.dbc`
- `j1939.dbc`
- `obd2.dbc`
- `fms.dbc`

O script Python `python/can_logger.py` carrega automaticamente TODOS os arquivos `.dbc` presentes nesta pasta ao iniciar!
Se você tiver múltiplos arquivos DBC, eles serão mesclados automaticamente para decodificar os PGNs/SPNs correspondentes.
