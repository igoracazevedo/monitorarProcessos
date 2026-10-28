# IAZ Jud - Sistema de Monitoramento Processual

## Visão Geral
Sistema full-stack para monitoramento de processos judiciais integrado diretamente ao Supabase via API REST. O front-end é uma aplicação web moderna em HTML5, Tailwind CSS e Vanilla JavaScript, com autenticação Google OAuth (PKCE) e controle de acesso restrito (whitelist de usuários liberados), permitindo gerenciar empresas, processos, status, relatórios e movimentações judiciais sem qualquer dependência do Google Apps Script.

## Pilha Tecnológica
- **Front-end**: HTML5, Tailwind CSS (Dark/Light mode), Vanilla JS, Supabase JS v2, XLSX, jsPDF, PWA (Service Worker e Manifest).
- **Autenticação & Controle de Acesso**: Supabase Auth (Google OAuth via PKCE) + Whitelist na tabela `ju_usuarios`.
- **Banco de Dados**: Supabase (PostgreSQL), tabelas identificadas e ordenadas pelo prefixo `ju_`.
- **Backend / Sincronizador**: Python 3 nativo (`sync_datajud.py` e `server.py`).
- **Automação em Nuvem**: GitHub Actions (`sync-processos.yml` a cada 2h e `deploy-pages.yml`).
- **Fonte Judiciária**: API Pública Oficial do DataJud (CNJ).

## Estrutura Principal de Tabelas no Supabase (Prefixo `ju_`)
1. **ju_usuarios**: Whitelist de controle de acesso isolada para o IAZ Jud (`email` [PK], `nome`, `papel`, `ativo`, `criado_em`).
   - `papel`: `'admin'` (acesso total e gestão de usuários) ou `'solicitante'` (operador/consulta).
   - `ativo`: `true` (liberado) ou `false` (bloqueado).
2. **ju_empresas**: Armazena filiais/clientes (`codigo`, `nome`, `logotipo`).
3. **ju_processos**: Armazena os autos (`processo`, `tribunal`, `status`, `apelido`, `empresa`, `reclamante`, `reclamado`, `vara`, `email`, `ultima_data`, `ultima_verificacao`).
4. **ju_movimentacoes**: Histórico detalhado por processo (`processo`, `data_movimentacao`, `atualizacao`).
5. **ju_configuracoes**: Parâmetros gerais do app (`chave`, `valor`).

## Autenticação e Controle de Acesso
- **Login com Google**:
  - Implementado via Supabase Auth com fluxo PKCE (`signInWithOAuth({ provider: 'google' })`).
  - Redirecionamento seguro para a origem atual (`window.location.origin + window.location.pathname`).
- **Whitelist de Acesso**:
  - Ao autenticar no Google, o app consulta o status do e-mail do usuário via RPC `papel_atual` e consulta à tabela `ju_usuarios`.
  - Se o usuário não estiver cadastrado ou com `ativo = false`, exibe a tela de **Acesso Não Autorizado** com opção de trocar de conta.
  - Se autorizado, libera o painel de processos e injeta o token JWT nas chamadas REST ao Supabase.
- **Gestão de Usuários Liberados (Exclusivo para Admins)**:
  - Menu lateral: **👥 Usuários Liberados** abre modal para adicionar novos e-mails, editar nomes/papéis, alternar entre Ativo/Bloqueado e excluir usuários.

## Rotinas de Sincronização Direta
- **`sync_datajud.py`**:
  - Script autônomo que consulta a API oficial do DataJud do CNJ usando chave pública.
  - Detecta o tribunal automaticamente pela máscara CNJ (TJCE, TRT7, TJSP, TRF5, etc.).
  - Implementa retry automático com backoff exponencial contra limitações de taxa (HTTP 429) e timeouts.
  - Grava no Supabase atualizando `ultima_verificacao` (ISO timestamp UTC), `ultima_data` e insere o lote de movimentações em `ju_movimentacoes`.
  - Fallback transparente: suporta tanto tabelas `ju_*` quanto legadas durante transições.
  - Executa na nuvem automaticamente a cada 2 horas via GitHub Actions.

- **`server.py`**:
  - Servidor HTTP e proxy CORS local na porta 8000 para desenvolvimento.

## Interface Web (`index.html`)
- **Telas**:
  - `authLoadingScreen`: Spinner de checagem inicial.
  - `loginScreen`: Card moderno com botão "Entrar com Google".
  - `semAcessoScreen`: Bloqueio amigável para e-mails não cadastrados.
  - `appLayout`: Painel principal com visão geral, filtros, histórico e exportação (Excel/PDF).
  - `usuariosModal`: Modal para administração de usuários liberados.
