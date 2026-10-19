# ADR 0003 — Endurecimento de segurança: auth na criação de eventos, origem na inscrição e IDs aleatórios

## Status

Aceito

## Data

2026-10-19

## Contexto

A revisão de segurança classificou como **MÉDIO** o fato de `POST /eventos`
(criação de eventos) aceitar requisições sem qualquer autenticação —
qualquer pessoa pode criar eventos arbitrários no sistema. Os ADRs 0001 e
0002 mantiveram essa rota pública por se tratar de projeto acadêmico, mas
recomendaram explicitamente exigir chave de administrador na criação para
uso em produção; esta decisão executa essa recomendação.

A rota pública de inscrição (`POST /eventos/{id}/inscricoes`) precisa
continuar pública — é a função central do sistema — mas requisições de
navegador originadas de páginas de terceiros (cross-site) permitem forjar
inscrições em nome de visitantes.

Por fim, os IDs de eventos e participantes eram contadores sequenciais
globais (`1, 2, 3...`), vazando o volume de registros e permitindo
enumeração trivial de recursos públicos.

## Decisão

1. **Auth na criação de eventos:** `POST /eventos` exige o header
   `X-Admin-Key` válido. A chave canônica é a variável de ambiente
   `EVENTREG_API_KEY`; a variável `ADMIN_API_KEY` (ADRs 0001/0002)
   continua aceita como fallback para não quebrar implantações
   existentes. Fail-closed: sem variável configurada, nada é autorizado.
   A comparação permanece com `hmac.compare_digest` (anti timing-attack).
2. **Validação de origem na inscrição:** a rota pública de inscrição
   rejeita (403) requisições de navegador cujo header `Origin` aponte
   para um host diferente do host da requisição. Clientes sem `Origin`
   (curl, aplicativos, testes) continuam permitidos.
3. **IDs aleatórios:** eventos e participantes passam a usar `uuid.uuid4()`
   (UUIDv4, biblioteca padrão). As rotas usam o conversor `<uuid:id>` do
   Flask, que responde 404 automaticamente para IDs malformados, e a
   igualdade de lookup é direta entre objetos UUID.

## Consequências

- **Positivas:** criação de eventos não pode ser abusada anonimamente;
  inscrições forjadas a partir de páginas de terceiros são bloqueadas;
  o volume de registros não vaza e a enumeração de IDs se torna
  impraticável; IDs malformados recebem 404 sem tocar a lista de eventos.
- **Negativas:** mudança de contrato da API — clientes que criavam eventos
  sem chave precisam configurar `EVENTREG_API_KEY` e enviar `X-Admin-Key`;
  IDs antes inteiros (`/eventos/1`) agora são UUIDs, exigindo atualização
  de clientes que montavam URLs manualmente.
- **Compatibilidade:** `ADMIN_API_KEY` existente continua funcionando; os
  testes foram atualizados (27 casos, todos passando) cobrindo auth
  fail-closed, fallback legado, origem cross-site e formato UUID.
- **Futuro:** para produção com múltiplos administradores, migrar para
  tokens de sessão com roles (conforme ADR 0001).
