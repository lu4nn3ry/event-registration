# ADR 0002 — Endurecimento da API: debugger, validação e concorrência

- **Status:** Aceito
- **Data:** 2026-10-12
- **Contexto:** Revisão de segurança semanal

## Contexto

A revisão semanal de segurança identificou que `app.py` era executado com
`app.run(debug=True)` — o único modo de execução documentado no README. O
debugger interativo do Werkzeug é um vetor conhecido de execução remota de
código: qualquer exceção não tratada serve uma página de traceback com
código-fonte, caminhos e versões, e o console (protegido por PIN que pode
ser derivado ou violado, cf. CVE-2024-34069) executa Python arbitrário —
incluindo a leitura de `ADMIN_API_KEY` do ambiente.

Três exceções não tratadas eram trivialmente alcançáveis, forçando a página
de debugger sob demanda:

1. `POST /eventos/<id>/inscricoes` sem `email` → `KeyError` → 500;
2. `POST /eventos` com `capacidade_maxima` não numérica → `TypeError` → 500;
3. `GET /eventos/<id>/inscricoes` com header `X-Admin-Key` não-ASCII
   (ex.: `café`) → `TypeError` em `hmac.compare_digest` → 500 —
   **disparável sem autenticação**, dentro da própria checagem de auth.

Adicionalmente: `Flask>=3.0` permitia instalar Werkzeug 3.0.x com CVEs
conhecidos, e o padrão check-then-act em `Evento.inscrever` não era
atômico (Flask roda com `threaded=True`), permitindo ultrapassar a
capacidade em requisições concorrentes.

## Decisão

1. **Debugger desativado por padrão:** `app.run` só habilita debug com
   `FLASK_DEBUG=1` explícito no ambiente. Produção deve usar servidor WSGI
   (gunicorn/uwsgi), onde o debugger nunca é montado.
2. **Validação de entrada em todas as rotas de escrita:** corpo deve ser
   objeto JSON; `nome`/`data` texto não vazio com limite de tamanho;
   `email` com formato mínimo válido; `capacidade_maxima` inteiro > 0
   (booleanos rejeitados). Entradas malformadas retornam **400** com
   mensagem de erro — nunca 500.
3. **Auth resiliente a headers não-ASCII:** `hmac.compare_digest` agora
   compara **bytes** (UTF-8), eliminando o crash não autenticado; qualquer
   falha de comparação falha fechado (403).
4. **Lotação atômica:** `Evento.inscrever` faz check + append sob
   `threading.Lock`, tornando a decisão de capacidade atômica.
5. **Floor de dependência corrigido:** `Flask>=3.1.3` (Werkzeug 3.1.x),
   eliminando as versões com CVE-2024-34069, CVE-2024-49766 e
   CVE-2024-49767 do intervalo instalável.

Mantida a decisão do ADR 0001 de manter `POST /eventos` público (projeto
acadêmico, sem dados pessoais expostos). Para uso em produção, recomenda-
se exigir a chave de administrador também na criação de eventos.

## Consequências

- **Positivas:** o debugger não pode mais ser forçado por entrada
  malformada; a API responde 400/403 previsíveis para entradas inválidas;
  a capacidade é garantida sob concorrência; o intervalo de dependências
  não inclui versões vulneráveis conhecidas.
- **Negativas:** chamadas que antes "funcionavam" com dados ausentes/inválidos
  (criando eventos com capacidade sem sentido) agora são rejeitadas;
  desenvolvedores precisam de `FLASK_DEBUG=1` para usar o debugger local.
- **Testes:** `tests/test_app.py` ganhou `TestValidacaoEntrada` (8 casos,
  incluindo o header não-ASCII) e `TestLotacaoConcorrente` (8 threads para
  capacidade 1 — exatamente 1 inscrição bem-sucedida).
