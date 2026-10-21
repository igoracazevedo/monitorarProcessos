# IAZ Jud - Sistema de Monitoramento Processual

## Visão Geral
Sistema full-stack para monitoramento de processos judiciais integrado diretamente ao Supabase via API REST. O front-end é uma aplicação web moderna em HTML5, Tailwind CSS e Vanilla JavaScript, permitindo gerenciar empresas, processos, status, relatórios e movimentações judiciais sem qualquer dependência do Google Apps Script.

## Pilha Tecnológica
- **Front-end**: HTML5, Tailwind CSS (Dark/Light mode), Vanilla JS, XLSX, jsPDF, PWA (Service Worker e Manifest).
- **Banco de Dados**: Supabase (PostgreSQL).
- **Backend / Sincronizador**: Python 3 nativo (`sync_datajud.py` e `server.py`).
- **Fonte Judiciária**: API Pública Oficial do DataJud (CNJ).

## Estrutura Principal de Tabelas no Supabase
1. **empresas**: Armazena filiais/clientes (`codigo`, `nome`, `logotipo`).
2. **processos**: Armazena os autos (`processo`, `tribunal`, `status`, `apelido`, `empresa`, `reclamante`, `reclamado`, `vara`, `email`, `ultima_data`, `ultima_verificacao`).
3. **movimentacoes**: Histórico detalhado por processo (`processo`, `data_movimentacao`, `atualizacao`).
4. **configuracoes**: Parâmetros gerais do app (`chave`, `valor`).

## Rotinas de Sincronização Direta
- **`sync_datajud.py`**:
  - Script autônomo que consulta a API oficial do DataJud do CNJ usando chave pública.
  - Detecta o tribunal automaticamente pela máscara CNJ (TJCE, TRT7, TJSP, TRF5, etc.).
  - Implementa retry automático com backoff exponencial contra limitações de taxa (HTTP 429) e timeouts.
  - Grava no Supabase atualizando `ultima_verificacao` (ISO timestamp UTC), `ultima_data` e insere o lote de movimentações em `movimentacoes`.
  - Exemplos de execução:
    - Sincronizar todos: `py sync_datajud.py`
    - Sincronizar pendentes: `py sync_datajud.py --pendentes`
    - Sincronizar processo único: `py sync_datajud.py --processo 00003004120255070009 --tribunal TRT7`
    - Modo daemon contínuo: `py sync_datajud.py --loop 3600` (roda a cada hora)

- **`server.py`**:
  - Servidor HTTP e proxy CORS local na porta 8000.
  - Serve o front-end web (`index.html`, PWA, etc.).
  - Endpoints:
    - `GET /api/status`: Diagnóstico de conectividade e Supabase.
    - `POST /api/consultar`: Consulta o DataJud e retorna dados do processo com CORS liberado.
    - `POST /api/sincronizar_processo`: Executa a sincronização completa de um processo no Supabase.
    - `POST /api/sincronizar_todos`: Executa sincronização em lote.

## Interface Web (`index.html`)
- **Exibição do Tribunal e Última Verificação**:
  - Cada processo na listagem exibe em linha:
    `[Número do Processo] [🏛️ Tribunal] [🕒 Verificado: DD/MM/AAAA às HH:MM]`
  - Processos ainda não verificados são destacados com indicação em âmbar `🕒 Verificado: Não verificado`.
- **Sincronização na UI**:
  - Botão individual **⚡ Atualizar**: sincroniza o processo via API local e atualiza em tempo real a tela e o histórico de movimentações.
  - Botão lateral **⚡ Checar DataJud (Todos)**: abre modal com barra de progresso visual (0% a 100%) e console de logs em tempo real para acompanhar a varredura completa.
- **Relatórios**:
  - Exportação para Excel (.xlsx) e PDF paisagem com coluna explícita de "Última Verificação".
