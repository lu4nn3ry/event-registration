# Recuperação - Sistema de Eventos

Sistema web (API) para cadastro de eventos, inscrições e controle de lotação.

## Tema

Eventos, inscrições e lotação (Team 5)

## Requisitos

- Python 3.10+
- Flask

## Instalação

```bash
pip install flask
```

## Execução

```bash
python app.py
```

> **Segurança:** o modo debug do Flask (debugger interativo do Werkzeug)
> fica **desativado** por padrão. Só é habilitado com a variável de ambiente
> `FLASK_DEBUG=1`, exclusivamente para desenvolvimento local.

> **Segurança:** para consultar `GET /eventos/{id}/inscricoes`, defina a
> variável de ambiente `ADMIN_API_KEY` e envie o header `X-Admin-Key` com
> o mesmo valor. Sem a variável configurada, o endpoint nega o acesso
> (fail-closed).

## Endpoints

### Eventos

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/eventos` | Criar evento |
| GET | `/eventos` | Listar eventos |
| GET | `/eventos/{id}` | Obter evento |

### Inscrições

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/eventos/{id}/inscricoes` | Inscrever participante |
| GET | `/eventos/{id}/inscricoes` | Listar inscrições |
| GET | `/eventos/{id}/lotacao` | Verificar lotação |

## Exemplos

### Criar evento

```bash
curl -X POST http://localhost:5000/eventos \
  -H "Content-Type: application/json" \
  -d '{"nome": "Workshop Python", "data": "2026-06-20", "capacidade_maxima": 3, "descricao": "Workshop de Python"}'
```

### Inscrever participante

```bash
curl -X POST http://localhost:5000/eventos/1/inscricoes \
  -H "Content-Type: application/json" \
  -d '{"nome": "Luann", "email": "luann@email.com"}'
```

### Verificar lotação

```bash
curl http://localhost:5000/eventos/1/lotacao
```
