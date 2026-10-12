"""Testes de segurança e funcionais da API de eventos."""

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def evento_com_inscricao(client):
    resp = client.post(
        "/eventos",
        json={"nome": "Workshop", "data": "2026-06-20", "capacidade_maxima": 5},
    )
    assert resp.status_code == 201
    evento_id = resp.get_json()["id"]
    resp = client.post(
        f"/eventos/{evento_id}/inscricoes",
        json={"nome": "Luann", "email": "luann@email.com"},
    )
    assert resp.status_code == 201
    return evento_id


class TestAcessoInscricoes:
    """GET /eventos/<id>/inscricoes exige X-Admin-Key (fail-closed)."""

    def test_sem_chave_configurada_negado(self, client, evento_com_inscricao,
                                          monkeypatch):
        monkeypatch.delenv("ADMIN_API_KEY", raising=False)
        resp = client.get(f"/eventos/{evento_com_inscricao}/inscricoes")
        assert resp.status_code == 403

    def test_sem_header_negado(self, client, evento_com_inscricao,
                               monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "secreta")
        resp = client.get(f"/eventos/{evento_com_inscricao}/inscricoes")
        assert resp.status_code == 403

    def test_chave_errada_negada(self, client, evento_com_inscricao,
                                 monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "secreta")
        resp = client.get(f"/eventos/{evento_com_inscricao}/inscricoes",
                          headers={"X-Admin-Key": "errada"})
        assert resp.status_code == 403

    def test_chave_correta_autorizada(self, client, evento_com_inscricao,
                                      monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "secreta")
        resp = client.get(f"/eventos/{evento_com_inscricao}/inscricoes",
                          headers={"X-Admin-Key": "secreta"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data[0]["email"] == "luann@email.com"


class TestEndpointsPublicos:
    """Endpoints públicos continuam funcionando normalmente."""

    def test_listar_eventos(self, client, evento_com_inscricao):
        resp = client.get("/eventos")
        assert resp.status_code == 200
        assert resp.get_json()[0]["nome"] == "Workshop"

    def test_lotacao_publica(self, client, evento_com_inscricao):
        resp = client.get(f"/eventos/{evento_com_inscricao}/lotacao")
        assert resp.status_code == 200
        assert resp.get_json()["vagas_ocupadas"] == 1

    def test_evento_inexistente(self, client):
        resp = client.get("/eventos/999")
        assert resp.status_code == 404


class TestValidacaoEntrada:
    """Entradas malformadas retornam 400, nunca 500 (sem debugger)."""

    def test_criar_evento_sem_nome(self, client):
        resp = client.post("/eventos", json={"data": "2026-06-20", "capacidade_maxima": 5})
        assert resp.status_code == 400

    def test_criar_evento_capacidade_string(self, client):
        resp = client.post(
            "/eventos",
            json={"nome": "W", "data": "2026-06-20", "capacidade_maxima": "tres"},
        )
        assert resp.status_code == 400

    def test_criar_evento_capacidade_negativa(self, client):
        resp = client.post(
            "/eventos",
            json={"nome": "W", "data": "2026-06-20", "capacidade_maxima": -1},
        )
        assert resp.status_code == 400

    def test_criar_evento_capacidade_booleana(self, client):
        resp = client.post(
            "/eventos",
            json={"nome": "W", "data": "2026-06-20", "capacidade_maxima": True},
        )
        assert resp.status_code == 400

    def test_criar_evento_sem_json(self, client):
        resp = client.post("/eventos", data="não é json", content_type="text/plain")
        assert resp.status_code == 400

    def test_inscricao_sem_email(self, client, evento_com_inscricao):
        resp = client.post(
            f"/eventos/{evento_com_inscricao}/inscricoes",
            json={"nome": "Luann"},
        )
        assert resp.status_code == 400

    def test_inscricao_email_invalido(self, client, evento_com_inscricao):
        resp = client.post(
            f"/eventos/{evento_com_inscricao}/inscricoes",
            json={"nome": "Luann", "email": "sem-arroba"},
        )
        assert resp.status_code == 400

    def test_chave_admin_nao_ascii_nao_crasha(self, client, evento_com_inscricao,
                                              monkeypatch):
        """Header não-ASCII no X-Admin-Key deve dar 403, não 500."""
        monkeypatch.setenv("ADMIN_API_KEY", "secreta")
        resp = client.get(
            f"/eventos/{evento_com_inscricao}/inscricoes",
            headers={"X-Admin-Key": "café"},
        )
        assert resp.status_code == 403


class TestLotacaoConcorrente:
    """A capacidade nunca pode ser ultrapassada, mesmo com concorrência."""

    def test_inscrever_concorrente_respeita_capacidade(self):
        """O check + append de inscrever() é atômico sob threads.

        (O test client do Flask não é thread-safe, então a atomicidade é
        exercitada diretamente no modelo — o mesmo código usado pela rota.)
        """
        import threading

        from app import Evento, Participante

        evento = Evento(1, "Lotado", "2026-06-20", capacidade_maxima=1)
        resultados = []
        lock = threading.Lock()

        def tentar_inscrever(i):
            ok, _ = evento.inscrever(Participante(i, f"P{i}", f"p{i}@email.com"))
            with lock:
                resultados.append(ok)

        threads = [
            threading.Thread(target=tentar_inscrever, args=(i,)) for i in range(16)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sum(1 for r in resultados if r) == 1
        assert len(evento.inscricoes) == 1
