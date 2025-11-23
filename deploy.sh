#!/bin/bash

# ShipTracker Prefect - Deploy Helper Script
# Facilita o deployment do flow com todas as configurações necessárias

set -e

echo "🚀 ShipTracker Prefect - Deploy Helper"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ Arquivo .env não encontrado!${NC}"
    echo "Copie o env-example para .env e configure as variáveis:"
    echo "  cp env-example .env"
    exit 1
fi

# Load .env
source .env

echo -e "${BLUE}📋 Configuração Atual:${NC}"
echo "  API_BASE_URL: $API_BASE_URL"
echo "  CRONJOB_API_KEY: ${CRONJOB_API_KEY:0:10}***"
echo ""

# Check if API_BASE_URL is localhost
if [[ $API_BASE_URL == *"127.0.0.1"* ]] || [[ $API_BASE_URL == *"localhost"* ]]; then
    echo -e "${YELLOW}⚠️  ATENÇÃO: API_BASE_URL está configurada como localhost!${NC}"
    echo "   O deploy não vai funcionar se o worker rodar em outro ambiente."
    echo ""
    read -p "   Deseja continuar mesmo assim? (s/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        echo "Deploy cancelado."
        exit 1
    fi
fi

echo -e "${BLUE}🎯 Escolha o método de deploy:${NC}"
echo "  1) Deploy Simples (variáveis via CLI)"
echo "  2) Deploy com Prefect Blocks (recomendado para produção)"
echo "  3) Apenas criar os Prefect Blocks"
echo "  4) Testar comunicação com a API"
echo ""
read -p "Opção [1-4]: " option

case $option in
    1)
        echo ""
        echo -e "${GREEN}📦 Deploy com variáveis via CLI${NC}"
        echo ""
        
        # Check work pools
        echo "Verificando work pools disponíveis..."
        
        # Check if default-work-pool exists directly
        if prefect work-pool inspect default-work-pool &>/dev/null; then
            echo -e "${GREEN}✓ Usando work pool 'default-work-pool' existente${NC}"
        else
            # List available pools
            echo "Work pools existentes:"
            prefect work-pool ls 2>/dev/null || true
            echo ""
            
            echo -e "${YELLOW}⚠️  Work pool 'default-work-pool' não encontrado${NC}"
            echo "Tentando criar..."
            
            if ! prefect work-pool create default-work-pool --type process 2>/dev/null; then
                echo -e "${RED}❌ Não foi possível criar work pool${NC}"
                echo ""
                echo "SOLUÇÃO: Use um work pool existente ou crie um via UI do Prefect"
                echo "Atualize o prefect.yaml com o nome do work pool disponível."
                exit 1
            fi
            
            echo -e "${GREEN}✓ Work pool 'default-work-pool' criado!${NC}"
        fi
        
        echo ""
        echo "Fazendo deploy do flow..."
        prefect deploy \
            --name ssw-tracking-sync \
            --pool default-work-pool \
            --variable API_BASE_URL="$API_BASE_URL" \
            --variable CRONJOB_API_KEY="$CRONJOB_API_KEY"
        
        echo ""
        echo -e "${GREEN}✅ Deploy concluído!${NC}"
        echo ""
        echo "Para executar o flow:"
        echo "  prefect deployment run ssw-tracking-sync/ssw-tracking-sync"
        echo ""
        echo "Para iniciar o worker:"
        echo "  prefect worker start --pool default-work-pool"
        ;;
        
    2)
        echo ""
        echo -e "${GREEN}📦 Deploy com Prefect Blocks${NC}"
        echo ""
        
        # Create secrets
        echo "Registrando tipos de blocks..."
        prefect block register -m prefect.blocks.system 2>/dev/null || true
        
        echo ""
        echo "Criando Prefect Secrets via Python..."
        python3 << EOF
from prefect.blocks.system import Secret

try:
    # API Base URL
    print("  → api-base-url")
    api_url = Secret(value="$API_BASE_URL")
    api_url.save("api-base-url", overwrite=True)
    print("     ✓ Criado/atualizado")
    
    # API Key
    print("  → cronjob-api-key")
    api_key = Secret(value="$CRONJOB_API_KEY")
    api_key.save("cronjob-api-key", overwrite=True)
    print("     ✓ Criado/atualizado")
except Exception as e:
    print(f"Erro: {e}")
    exit(1)
EOF
        
        if [ $? -ne 0 ]; then
            echo ""
            echo -e "${RED}❌ Erro ao criar secrets${NC}"
            exit 1
        fi
        
        echo ""
        echo "Secrets criados com sucesso!"
        
        # Check work pools
        echo ""
        echo "Verificando work pools disponíveis..."
        
        # Check if default-work-pool exists directly
        if prefect work-pool inspect default-work-pool &>/dev/null; then
            echo -e "${GREEN}✓ Usando work pool 'default-work-pool' existente${NC}"
        else
            # List available pools
            echo "Work pools existentes:"
            prefect work-pool ls 2>/dev/null || true
            echo ""
            
            echo -e "${YELLOW}⚠️  Work pool 'default-work-pool' não encontrado${NC}"
            echo "Tentando criar..."
            
            if ! prefect work-pool create default-work-pool --type process 2>/dev/null; then
                echo -e "${RED}❌ Não foi possível criar work pool${NC}"
                echo ""
                echo "SOLUÇÃO: Use um work pool existente ou crie um via UI do Prefect"
                echo "Atualize o prefect.yaml com o nome do work pool disponível."
                exit 1
            fi
            
            echo -e "${GREEN}✓ Work pool 'default-work-pool' criado!${NC}"
        fi
        
        echo ""
        echo "Fazendo deploy do flow..."
        prefect deploy --all
        
        echo ""
        echo -e "${GREEN}✅ Deploy concluído!${NC}"
        echo ""
        echo "Secrets criados:"
        echo "  • api-base-url: $API_BASE_URL"
        echo "  • cronjob-api-key: ${CRONJOB_API_KEY:0:10}***"
        echo ""
        echo "Para executar o flow:"
        echo "  prefect deployment run ssw-tracking-sync/ssw-tracking-sync"
        echo ""
        echo "Para iniciar o worker:"
        echo "  prefect worker start --pool default-work-pool"
        ;;
        
    3)
        echo ""
        echo -e "${GREEN}🔐 Criando apenas os Prefect Blocks${NC}"
        echo ""
        
        echo "Registrando tipos de blocks..."
        prefect block register -m prefect.blocks.system 2>/dev/null || true
        
        echo ""
        echo "Criando secrets via Python..."
        python3 << EOF
from prefect.blocks.system import Secret
import sys

try:
    # API Base URL
    print("  → api-base-url")
    try:
        api_url = Secret(value="$API_BASE_URL")
        api_url.save("api-base-url", overwrite=True)
        print("     ✓ Criado/atualizado")
    except Exception as e:
        print(f"     ⚠ Erro: {e}")
    
    # API Key
    print("  → cronjob-api-key")
    try:
        api_key = Secret(value="$CRONJOB_API_KEY")
        api_key.save("cronjob-api-key", overwrite=True)
        print("     ✓ Criado/atualizado")
    except Exception as e:
        print(f"     ⚠ Erro: {e}")
    
    sys.exit(0)
except Exception as e:
    print(f"Erro geral: {e}")
    sys.exit(1)
EOF
        
        if [ $? -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✅ Blocks criados com sucesso!${NC}"
        else
            echo ""
            echo -e "${RED}❌ Erro ao criar blocks${NC}"
            echo "Tente criar manualmente via UI do Prefect:"
            echo "https://app.prefect.cloud/account/.../blocks"
            exit 1
        fi
        
        echo ""
        echo "Você pode verificar os blocks em:"
        echo "  prefect block ls"
        ;;
        
    4)
        echo ""
        echo -e "${GREEN}🧪 Testando comunicação com a API${NC}"
        echo ""
        
        echo "1️⃣  Testando conectividade..."
        if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${API_BASE_URL}/health" | grep -q "200\|404"; then
            echo -e "   ${GREEN}✅ API está acessível${NC}"
        else
            echo -e "   ${RED}❌ API não está acessível${NC}"
            echo "   URL: ${API_BASE_URL}/health"
            exit 1
        fi
        
        echo ""
        echo "2️⃣  Testando autenticação..."
        response=$(curl -s -w "\n%{http_code}" -X GET \
            "${API_BASE_URL}/tracking-updates/occurrence-codes" \
            -H "X-API-Key: $CRONJOB_API_KEY" \
            --max-time 5)
        
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | head -n-1)
        
        if [ "$http_code" = "200" ]; then
            echo -e "   ${GREEN}✅ Autenticação funcionando${NC}"
            echo "   Códigos de ocorrência disponíveis: $(echo "$body" | grep -o '"code"' | wc -l)"
        elif [ "$http_code" = "401" ]; then
            echo -e "   ${RED}❌ Erro de autenticação (401 Unauthorized)${NC}"
            echo "   Verifique se CRONJOB_API_KEY está correta"
            exit 1
        else
            echo -e "   ${YELLOW}⚠️  Status HTTP: $http_code${NC}"
            echo "   Response: ${body:0:200}"
        fi
        
        echo ""
        echo "3️⃣  Testando endpoint de remessas pendentes..."
        response=$(curl -s -w "\n%{http_code}" -X GET \
            "${API_BASE_URL}/tracking-updates/pending-shipments" \
            -H "X-API-Key: $CRONJOB_API_KEY" \
            --max-time 5)
        
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | head -n-1)
        
        if [ "$http_code" = "200" ]; then
            echo -e "   ${GREEN}✅ Endpoint de remessas pendentes funcionando${NC}"
            count=$(echo "$body" | grep -o '"invoice_number"' | wc -l)
            echo "   Remessas pendentes encontradas: $count"
        else
            echo -e "   ${YELLOW}⚠️  Status HTTP: $http_code${NC}"
            echo "   Response: ${body:0:200}"
        fi
        
        echo ""
        echo -e "${GREEN}✅ Testes concluídos!${NC}"
        echo ""
        echo "A API está pronta para receber requisições do Prefect."
        ;;
        
    *)
        echo "Opção inválida!"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}📚 Recursos Úteis:${NC}"
echo "  • Ver deployments: prefect deployment ls"
echo "  • Ver work pools: prefect work-pool ls"
echo "  • Ver blocks: prefect block ls"
echo "  • Logs do flow: prefect deployment logs ssw-tracking-sync/ssw-tracking-sync"
echo "  • UI do Prefect: prefect server start (ou acesse Prefect Cloud)"
echo ""
