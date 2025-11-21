# ShipTracker Prefect - SSW Tracking Sync

Orchestração de pipelines de rastreamento usando [Prefect](https://www.prefect.io/).

## 📋 Descrição

Este projeto contém flows do Prefect para sincronização automática de dados de rastreamento de remessas da transportadora SSW com a API do ShipTracker.

## 🚀 Funcionalidades

- **Busca automática** de remessas pendentes via API
- **Web scraping** do site da SSW para obter dados de rastreamento
- **Extração estruturada** de eventos de rastreamento (unidade, localização, data/hora, status, código de ocorrência)
- **Atualização automática** na API usando endpoints de tracking-updates
- **Autenticação flexível** (JWT ou API Key)
- **Logs detalhados** de cada operação

## ⚙️ Configuração

### 1. Variáveis de Ambiente

Copie o arquivo `.env.example` para `.env`:

```bash
cp .env.example .env
```

Configure as variáveis:

```bash
# URL da API
API_BASE_URL=http://127.0.0.1:8000/api/v1

# API Key para autenticação do cronjob
# Gerar com: python -c "import secrets; print(secrets.token_urlsafe(32))"
CRONJOB_API_KEY=sua-api-key-aqui
```

### 2. Dependências

Instale as dependências do projeto:

```bash
uv sync
```

## 🏃 Execução

### Execução Manual

Execute o flow uma vez:

```bash
uv run python main.py
```

### Deploy com Agendamento

Para executar periodicamente (ex: a cada 15 minutos):

```python
# Descomente no main.py:
sync_ssw_tracking.serve(
    name="ssw-tracking-sync",
    cron="*/15 * * * *"  # A cada 15 minutos
)
```

Execute:

```bash
uv run python main.py
```

## 📊 Fluxo de Dados

```
1. Buscar Remessas Pendentes → 2. Scrape SSW Website → 3. Extrair Eventos → 4. Atualizar API → 5. Logs
```

### Detalhes do Processo

1. **Busca de Remessas**: GET `/api/v1/tracking-updates/pending-shipments` (com API Key)
2. **Web Scraping**: POST `https://ssw.inf.br/2/resultSSW_dest_nro`
3. **Extração de Dados**:
   - Unidade operacional (código 4 dígitos)
   - Localização (cidade/estado)
   - Data/hora do evento
   - Status e código de ocorrência
   - Protocolo SEFAZ
4. **Atualização**: POST `/api/v1/tracking-updates/shipment`

## 🔐 Autenticação

O flow usa **API Key** para autenticação:

```bash
# Gerar API Key segura
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Configure a mesma API Key em:
- `.env` do Prefect → `CRONJOB_API_KEY`
- `.env` da API → `CRONJOB_API_KEY`

## 📝 Estrutura de Dados

### Dados Enviados à API

```json
{
  "tracking_code": null,
  "invoice_number": "123456",
  "document": "12345678000199",
  "carrier": "SSW",
  "current_status": "Em trânsito",
  "events": [
    {
      "occurrence_code": "01",
      "status": "Nota Fiscal Eletrônica emitida",
      "description": "Nota Fiscal Eletrônica emitida  01",
      "location": "São Paulo SP",
      "unit": "0001",
      "occurred_at": "2025-11-20T14:30:00",
      "raw_data": "..."
    }
  ],
  "last_update": "2025-11-20T15:00:00"
}
```

## 🐛 Troubleshooting

### Erro de Autenticação
```
HTTP 401 Unauthorized
```
**Solução**: Verifique se a `CRONJOB_API_KEY` está configurada corretamente em ambos `.env` (API e Prefect)

### Sem Dados de Rastreamento
```
No tracking data found
```
**Possíveis causas**:
- Nota fiscal não encontrada no SSW
- CPF/CNPJ incorreto
- HTML do SSW mudou (verificar estrutura)

### Timeout
```
Error scraping tracking
```
**Solução**: Aumente o timeout nas requisições (padrão: 10s)

## 📦 Dependências

- `prefect` - Orquestração de workflows
- `httpx` - Cliente HTTP moderno com suporte async
- `beautifulsoup4` - Parsing de HTML
- `html5lib` - Parser HTML5

## 🔄 Exemplos de Uso

### Execução Única
```bash
uv run python main.py
```

### Agendar Execução (Cron)
```bash
# A cada 15 minutos
cron="*/15 * * * *"

# Todo dia às 8h
cron="0 8 * * *"

# A cada hora
cron="0 * * * *"
```
