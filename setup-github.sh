#!/bin/bash

# Script para configurar GitHub como source do código para Prefect Cloud

set -e

echo "🚀 Setup GitHub para Prefect Cloud"
echo "===================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if we're in a git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Não é um repositório git!${NC}"
    echo ""
    echo "Inicialize o git primeiro:"
    echo "  git init"
    echo "  git add ."
    echo "  git commit -m 'Initial commit'"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Você tem alterações não commitadas${NC}"
    echo ""
    git status --short
    echo ""
    read -p "Deseja commitá-las agora? (s/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        git add .
        read -p "Mensagem do commit: " commit_msg
        git commit -m "${commit_msg:-Update Prefect flow}"
    else
        echo "Por favor, commite as alterações primeiro."
        exit 1
    fi
fi

# Check if remote exists
if ! git remote get-url origin > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Nenhum remote 'origin' configurado${NC}"
    echo ""
    echo "Configure o remote do GitHub:"
    read -p "URL do repositório GitHub (ex: https://github.com/user/repo.git): " repo_url
    
    if [ -z "$repo_url" ]; then
        echo "URL não pode ser vazia!"
        exit 1
    fi
    
    git remote add origin "$repo_url"
    echo -e "${GREEN}✓ Remote 'origin' adicionado${NC}"
fi

# Get current remote
REMOTE_URL=$(git remote get-url origin)
echo -e "${BLUE}📦 Repositório:${NC} $REMOTE_URL"
echo ""

# Check if repo is private
echo -e "${YELLOW}⚠️  Importante:${NC}"
echo "   • Se o repositório for PRIVADO, você precisa de um token"
echo "   • Se for PÚBLICO, não precisa de token"
echo ""

read -p "O repositório é privado? (s/N): " -n 1 -r
echo
IS_PRIVATE=$([[ $REPLY =~ ^[Ss]$ ]] && echo "true" || echo "false")

if [ "$IS_PRIVATE" = "true" ]; then
    echo ""
    echo -e "${BLUE}🔐 Configurando GitHub Token...${NC}"
    echo ""
    echo "1. Vá em: https://github.com/settings/tokens"
    echo "2. Clique em 'Generate new token' (classic)"
    echo "3. Selecione scope: 'repo' (acesso completo a repositórios privados)"
    echo "4. Gere o token e copie"
    echo ""
    read -p "Cole o GitHub Token aqui: " github_token
    
    if [ -z "$github_token" ]; then
        echo "Token não pode ser vazio!"
        exit 1
    fi
    
    # Create GitHub Credentials Block
    echo ""
    echo "Criando GitHub Credentials Block no Prefect..."
    
    python3 << EOF
from prefect.blocks.system import Secret
from prefect_github import GitHubCredentials

try:
    # Create GitHub credentials block
    github_creds = GitHubCredentials(token=Secret(value="$github_token"))
    github_creds.save("github-token", overwrite=True)
    print("✓ GitHub Credentials criado!")
except Exception as e:
    print(f"Erro: {e}")
    exit(1)
EOF
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ GitHub Credentials configurado${NC}"
        
        # Update prefect.yaml to use the token
        sed -i 's/access_token: null/access_token: "{{ prefect.blocks.github-credentials.github-token }}"/' prefect.yaml
        echo "✓ prefect.yaml atualizado para usar o token"
    else
        echo -e "${RED}❌ Erro ao criar GitHub Credentials${NC}"
        exit 1
    fi
fi

# Push to GitHub
echo ""
echo -e "${BLUE}📤 Fazendo push para GitHub...${NC}"

BRANCH=$(git branch --show-current)
echo "Branch atual: $BRANCH"

if git push -u origin "$BRANCH" 2>&1; then
    echo -e "${GREEN}✓ Push realizado com sucesso!${NC}"
else
    echo -e "${RED}❌ Erro no push${NC}"
    echo ""
    echo "Tente fazer push manualmente:"
    echo "  git push -u origin $BRANCH"
    exit 1
fi

# Update prefect.yaml with correct repo URL and branch
echo ""
echo -e "${BLUE}📝 Atualizando prefect.yaml...${NC}"

# Extract repo path from URL
REPO_PATH=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/](.+)(\.git)?$|\1|' | sed 's|\.git$||')

# Update repository and branch in prefect.yaml
sed -i "s|repository: .*|repository: https://github.com/$REPO_PATH.git|" prefect.yaml
sed -i "s|branch: .*|branch: $BRANCH|" prefect.yaml

echo -e "${GREEN}✓ prefect.yaml atualizado${NC}"
echo "   Repository: https://github.com/$REPO_PATH.git"
echo "   Branch: $BRANCH"

# Re-deploy
echo ""
echo -e "${BLUE}🚀 Fazendo re-deploy no Prefect Cloud...${NC}"
echo ""

if ./deploy.sh << EOF
2
EOF
then
    echo ""
    echo -e "${GREEN}✅ Setup completo!${NC}"
    echo ""
    echo -e "${BLUE}📊 O que acontece agora:${NC}"
    echo "   1. Prefect Cloud baixa o código do GitHub automaticamente"
    echo "   2. O Managed Worker executa o flow no ambiente Prefect"
    echo "   3. O schedule roda a cada hora (*/60 * * * *)"
    echo ""
    echo -e "${GREEN}🎯 Próximos passos:${NC}"
    echo ""
    echo "1. Vá para o Prefect Cloud UI:"
    echo "   https://app.prefect.cloud"
    echo ""
    echo "2. Execute o flow manualmente para testar:"
    echo "   prefect deployment run sync_ssw_tracking/ssw-tracking-sync"
    echo ""
    echo "3. Monitore a execução no Prefect Cloud UI"
    echo ""
    echo -e "${YELLOW}💡 Importante:${NC}"
    echo "   • A cada mudança no código, faça commit e push"
    echo "   • O Prefect baixa a versão mais recente do branch"
    echo "   • Não precisa fazer deploy novamente, só push!"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Erro no re-deploy${NC}"
    echo ""
    echo "Tente manualmente:"
    echo "  ./deploy.sh"
    exit 1
fi
