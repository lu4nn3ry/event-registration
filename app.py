import hmac
import os
import threading

from flask import Flask, jsonify, request


app = Flask(__name__)


def _chave_admin_configurada():
    return os.environ.get("ADMIN_API_KEY", "")


def _admin_autorizado():
    """Valida o header X-Admin-Key contra ADMIN_API_KEY (fail-closed).

    Sem a variável de ambiente configurada, nenhuma requisição é autorizada.
    A comparação usa hmac.compare_digest sobre bytes para evitar timing
    attacks e TypeError com caracteres não-ASCII no header (que crasharia
    a rota com 500 antes da correção).
    """
    chave_esperada = _chave_admin_configurada()
    if not chave_esperada:
        return False
    chave_recebida = request.headers.get("X-Admin-Key", "")
    try:
        return hmac.compare_digest(
            chave_recebida.encode("utf-8", errors="replace"),
            chave_esperada.encode("utf-8"),
        )
    except TypeError:
        return False


def _json_body():
    """Exige um objeto JSON no corpo; retorna (dados, None) ou (None, resposta 400)."""
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return None, (jsonify({"erro": "Corpo da requisição deve ser um objeto JSON"}), 400)
    return dados, None


def _campo_texto(dados, campo, max_len=200):
    """Valida presença/tipo/tamanho de um campo de texto; retorna (valor, erro)."""
    valor = dados.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        return None, f"Campo '{campo}' é obrigatório e deve ser texto não vazio"
    if len(valor) > max_len:
        return None, f"Campo '{campo}' excede o limite de {max_len} caracteres"
    return valor.strip(), None


def _campo_email(dados, campo="email", max_len=320):
    valor, erro = _campo_texto(dados, campo, max_len)
    if erro:
        return None, erro
    if "@" not in valor or valor.startswith("@") or valor.endswith("@") or " " in valor:
        return None, f"Campo '{campo}' deve ser um e-mail válido"
    return valor, None


def _campo_capacidade(dados, campo="capacidade_maxima"):
    valor = dados.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        return None, f"Campo '{campo}' deve ser um inteiro maior que zero"
    return valor, None


class Evento:
    def __init__(self, id, nome, data, capacidade_maxima, descricao=""):
        self.id = id
        self.nome = nome
        self.data = data
        self.capacidade_maxima = capacidade_maxima
        self.descricao = descricao
        self.inscricoes = []
        self._lock = threading.Lock()

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "data": self.data,
            "capacidade_maxima": self.capacidade_maxima,
            "descricao": self.descricao,
            "vagas_disponiveis": self.capacidade_maxima - len(self.inscricoes),
        }

    def inscrever(self, participante):
        # Check + append atômicos: sem a lock, requisições concorrentes
        # poderiam ultrapassar a capacidade (check-then-act race).
        with self._lock:
            if len(self.inscricoes) >= self.capacidade_maxima:
                return False, "Evento lotado"

            self.inscricoes.append(participante)
            return True, "Inscricao realizada com sucesso"

    def verificar_lotacao(self):
        vagas_ocupadas = len(self.inscricoes)
        return {
            "evento": self.nome,
            "capacidade_maxima": self.capacidade_maxima,
            "vagas_ocupadas": vagas_ocupadas,
            "vagas_disponiveis": self.capacidade_maxima - vagas_ocupadas,
            "status": "lotado" if vagas_ocupadas >= self.capacidade_maxima else "disponivel",
        }


class Participante:
    def __init__(self, id, nome, email):
        self.id = id
        self.nome = nome
        self.email = email

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "email": self.email,
        }


db_eventos = []
id_evento_seq = 1
id_participante_seq = 1


@app.post("/eventos")
def criar_evento():
    global id_evento_seq
    dados, resposta = _json_body()
    if resposta:
        return resposta
    nome, erro = _campo_texto(dados, "nome")
    if erro:
        return jsonify({"erro": erro}), 400
    data, erro = _campo_texto(dados, "data")
    if erro:
        return jsonify({"erro": erro}), 400
    capacidade_maxima, erro = _campo_capacidade(dados)
    if erro:
        return jsonify({"erro": erro}), 400
    descricao = dados.get("descricao", "")
    if not isinstance(descricao, str):
        return jsonify({"erro": "Campo 'descricao' deve ser texto"}), 400
    evento = Evento(id_evento_seq, nome, data, capacidade_maxima, descricao)
    db_eventos.append(evento)
    id_evento_seq += 1
    return jsonify(evento.to_dict()), 201


@app.get("/eventos")
def listar_eventos():
    return jsonify([e.to_dict() for e in db_eventos])


@app.get("/eventos/<int:id>")
def obter_evento(id):
    evento = next((e for e in db_eventos if e.id == id), None)
    if not evento:
        return jsonify({"erro": "Evento nao encontrado"}), 404
    return jsonify(evento.to_dict())


@app.post("/eventos/<int:id>/inscricoes")
def inscrever_participante(id):
    global id_participante_seq
    evento = next((e for e in db_eventos if e.id == id), None)
    if not evento:
        return jsonify({"erro": "Evento nao encontrado"}), 404
    dados, resposta = _json_body()
    if resposta:
        return resposta
    nome, erro = _campo_texto(dados, "nome")
    if erro:
        return jsonify({"erro": erro}), 400
    email, erro = _campo_email(dados)
    if erro:
        return jsonify({"erro": erro}), 400
    participante = Participante(id_participante_seq, nome, email)
    sucesso, mensagem = evento.inscrever(participante)
    if not sucesso:
        return jsonify({"erro": mensagem}), 400
    id_participante_seq += 1
    return jsonify({"mensagem": mensagem, "participante": participante.to_dict()}), 201


@app.get("/eventos/<int:id>/inscricoes")
def listar_inscricoes(id):
    if not _admin_autorizado():
        return jsonify({"erro": "Acesso restrito a administradores"}), 403
    evento = next((e for e in db_eventos if e.id == id), None)
    if not evento:
        return jsonify({"erro": "Evento nao encontrado"}), 404
    return jsonify([p.to_dict() for p in evento.inscricoes])


@app.get("/eventos/<int:id>/lotacao")
def verificar_lotacao(id):
    evento = next((e for e in db_eventos if e.id == id), None)
    if not evento:
        return jsonify({"erro": "Evento nao encontrado"}), 404
    return jsonify(evento.verificar_lotacao())


if __name__ == "__main__":
    # O debugger interativo do Werkzeug nunca deve ser habilitado por padrão:
    # qualquer exceção não tratada expõe código-fonte e, com o PIN violado,
    # permite execução remota de código. Só ativa com FLASK_DEBUG=1 explícito.
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
