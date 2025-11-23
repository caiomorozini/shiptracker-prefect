#!/bin/bash

# Script para configurar work pool local (process) no lugar do managed

set -e

echo "🔧 Configurando Work Pool Local para Prefect"
echo "============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}📋 Work Pools Atuais:${NC}"
prefect work-pool ls
echo ""

echo -e "${YELLOW}⚠️  Você está usando 'default-work-pool' que é do tipo 'managed'${NC}"
echo "   Managed pools executam código no ambiente Prefect Cloud."
echo "   Para desenvolvimento local, é melhor usar 'process' pool."
echo ""

read -p "Deseja criar um work pool local? (s/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "Operação cancelada."
    exit 0
fi

# Nome do novo pool
POOL_NAME="local-pool"

# Check if pool already exists
if prefect work-pool inspect "$POOL_NAME" &>/dev/null; then
    echo -e "${GREEN}✓ Work pool '$POOL_NAME' já existe${NC}"
else
    echo ""
    echo "Criando work pool '$POOL_NAME' (tipo: process)..."
    
    # Try to create
    if prefect work-pool create "$POOL_NAME" --type process 2>&1; then
        echo -e "${GREEN}✓ Work pool '$POOL_NAME' criado!${NC}"
    else
        echo -e "${RED}❌ Erro ao criar work pool${NC}"
        echo ""
        echo "Você pode estar no limite do plano (1 work pool)."
        echo ""
        echo "Opções:"
        echo "  1. Delete o work pool 'default-work-pool' e tente novamente"
        echo "  2. Use o work pool existente (atualize manualmente o prefect.yaml)"
        echo "  3. Faça upgrade do plano Prefect Cloud"
        exit 1
    fi
fi

echo ""
echo -e "${BLUE}📝 Atualizando prefect.yaml...${NC}"

# Backup
cp prefect.yaml prefect.yaml.backup
echo "   Backup criado: prefect.yaml.backup"

# Update prefect.yaml
sed -i "s/name: default-work-pool/name: $POOL_NAME/" prefect.yaml
echo -e "${GREEN}   ✓ prefect.yaml atualizado${NC}"

echo ""
echo -e "${BLUE}🚀 Fazendo re-deploy...${NC}"

# Re-deploy
if ./deploy.sh << EOF
2
EOF
then
    echo ""
    echo -e "${GREEN}✅ Configuração concluída!${NC}"
    echo ""
    echo -e "${BLUE}📚 Próximos passos:${NC}"
    echo ""
    echo "1. Inicie o worker LOCAL (deixe rodando):"
    echo -e "   ${YELLOW}prefect worker start --pool $POOL_NAME${NC}"
    echo ""
    echo "2. Em outro terminal, execute o flow:"
    echo "   prefect deployment run sync_ssw_tracking/ssw-tracking-sync"
    echo ""
    echo "3. Ou deixe o schedule automático rodar a cada hora"
    echo ""
    echo -e "${GREEN}💡 Dica:${NC} Para manter o worker rodando em background, use:"
    echo "   nohup prefect worker start --pool $POOL_NAME > worker.log 2>&1 &"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Erro no re-deploy${NC}"
    echo "Restaurando backup..."
    mv prefect.yaml.backup prefect.yaml
    exit 1
fi
