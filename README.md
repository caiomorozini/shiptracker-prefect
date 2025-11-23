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

### Execução Manual (Local)

Execute o flow uma vez localmente:

```bash
uv run python main.py
```

### 🚀 Deploy para Produção

⚠️ **IMPORTANTE**: Quando fizer deploy no Prefect Cloud/Server, o código roda em um worker remoto que **não tem acesso ao localhost**!

#### Deploy Rápido (Assistido)

Use o script helper:

```bash
./deploy.sh
```

O script oferece 4 opções:
1. Deploy simples (variáveis via CLI)
2. Deploy com Prefect Blocks (recomendado para produção)
3. Criar apenas os Prefect Blocks
4. Testar comunicação com a API

#### Deploy Manual

```bash
# Opção 1: Via CLI com variáveis
prefect deploy \
  --name ssw-tracking-sync \
  --pool default-pool \
  --variable API_BASE_URL=https://sua-api.com/api/v1 \
  --variable CRONJOB_API_KEY=sua-api-key

# Opção 2: Via Blocks (recomendado)
# 1. Criar secrets
prefect block create secret api-base-url --value "https://sua-api.com/api/v1"
prefect block create secret cronjob-api-key --value "sua-api-key"

# 2. Deploy
prefect deploy --all

# 3. Iniciar worker
prefect worker start --pool default-pool
```

📚 **Guia Completo**: Veja [DEPLOYMENT.md](./DEPLOYMENT.md) para instruções detalhadas

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

### 🔴 Prefect não consegue se comunicar com a API após deploy

**Sintoma**: O flow funciona localmente mas falha após o deploy
```
httpx.ConnectError: [Errno 111] Connection refused
```

**Causa**: O código roda em um worker remoto que não tem acesso ao `localhost` (127.0.0.1)

**Solução**:
1. Configure `API_BASE_URL` com a URL pública da API (ex: `https://sua-api.com/api/v1`)
2. Use Prefect Blocks ou variáveis de ambiente no deployment
3. Veja o guia completo em [DEPLOYMENT.md](./DEPLOYMENT.md)

**Teste rápido**:
```bash
./deploy.sh  # Escolha opção 4 para testar comunicação
```

### 🔴 FileNotFoundError: No such file or directory

**Sintoma**: 
```
FileNotFoundError: [Errno 2] No such file or directory: '/home/caiomorozini/Dev/shiptracker/shiptracker-prefect'
```

**Causa**: Você está usando um **Managed Work Pool** que executa no ambiente Prefect Cloud, não localmente.

**Solução RÁPIDA**:
```bash
# Rode o worker LOCALMENTE
cd /home/caiomorozini/Dev/shiptracker/shiptracker-prefect
source .venv/bin/activate
prefect worker start --pool default-work-pool

# Em outro terminal, execute o flow
prefect deployment run sync_ssw_tracking/ssw-tracking-sync
```

📚 **Guia Completo**: [SOLUCAO_RAPIDA.md](./SOLUCAO_RAPIDA.md)

**Solução PRODUÇÃO**: Veja [PREFECT_MANAGED_WORKER.md](./PREFECT_MANAGED_WORKER.md) para configurar GitHub ou Docker

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
