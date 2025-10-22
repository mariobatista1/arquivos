# playercore_retain/backend/Dockerfile

# Dockerfile para Backend NestJS - PlayerCore Retain
FROM node:20-alpine AS base

# Instalar dependências necessárias
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Estágio de build
FROM base AS build

WORKDIR /app

# Copiar arquivos de dependência primeiro
COPY package*.json ./

# Instalar TODAS as dependências (incluindo dev) para o build
RUN npm install --legacy-peer-deps

# Copiar código fonte
COPY . .

# Instalar type definitions específicos que estão faltando
RUN npm install --save-dev @types/jest @types/node @types/multer @types/express

# Build da aplicação
RUN npm run build

# Estágio de produção
FROM base AS production

WORKDIR /app

# Copiar arquivos de dependência
COPY package*.json ./

# Instalar apenas dependências de produção
RUN npm install --legacy-peer-deps --omit=dev

# Copiar aplicação buildada
COPY --from=build /app/dist ./dist

# Criar usuário não-root para segurança
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nestjs -u 1001

# Mudar ownership dos arquivos
RUN chown -R nestjs:nodejs /app
USER nestjs

# Expor porta
EXPOSE 3000

# Health check (se você tiver o arquivo healthcheck.js)
# HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
#   CMD node healthcheck.js

# Comando de inicialização
CMD ["node", "dist/main"]