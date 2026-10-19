"""Testes de segurança e funcionais da API de eventos."""

import uuid

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def chave_admin(monkeypatch):
    monkeypatch.setenv("EVENTREG_API_KEY", "secreta")
    return {"X-Admin-Key": "secreta"}


@pytest.fixture
def evento_com_inscricao(client, chave_admin):
    resp = client.post(
        "/eventos",
        json={"nome": "Workshop", "data": "2026-06-20", "capacidade_maxima": 5},
        headers=chave_admin,
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

    def test_criar_evento_sem_nome(self, client, chave_admin):
        resp = client.post(
            "/eventos",
            json={"data": "2026-06-20", "capacidade_maxima": 5},
            headers=chave_admin,
        )
        assert resp.status_code == 400

    def test_criar_evento_capacidade_string(self, client, chave_admin):
        resp = client.post(
            "/eventos",
            json={"nome": "W", "data": "2026-06-20", "capacidade_maxima": "tres"},
            headers=chave_admin,
        )
        assert resp.status_code == 400

    def test_criar_evento_capacidade_negativa(self, client, chave_admin):
        resp = client.post(
            "/eventos",
            json={"nome": "W", "data": "2026-06-20", "capacidade_maxima": -1},
            headers=chave_admin,
        )
        assert resp.status_code == 400

    def test_criar_evento_capacidade_booleana(self, client, chave_admin):
        resp = client.post(
            "/eventos",
            json={"nome": "W", "data": "2026-06-20", "capacidade_maxima": True},
            headers=chave_admin,
        )
        assert resp.status_code == 400

    def test_criar_evento_sem_json(self, client, chave_admin):
        resp = client.post(
            "/eventos",
            data="não é json",
            content_type="text/plain",
            headers=chave_admin,
        )
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


class TestAuthCriacaoEventos:
    """POST /eventos exige X-Admin-Key (fail-closed)."""

    payload = {"nome": "W", "data": "2026-06-20", "capacidade_maxima": 5}

    def test_sem_chave_configurada_negado(self, client, monkeypatch):
        monkeypatch.delenv("EVENTREG_API_KEY", raising=False)
        monkeypatch.delenv("ADMIN_API_KEY", raising=False)
        resp = client.post("/eventos", json=self.payload)
        assert resp.status_code == 403

    def test_sem_header_negado(self, client, monkeypatch):
        monkeypatch.setenv("EVENTREG_API_KEY", "secreta")
        resp = client.post("/eventos", json=self.payload)
        assert resp.status_code == 403

    def test_chave_errada_negada(self, client, monkeypatch):
        monkeypatch.setenv("EVENTREG_API_KEY", "secreta")
        resp = client.post(
            "/eventos", json=self.payload, headers={"X-Admin-Key": "errada"}
        )
        assert resp.status_code == 403

    def test_chave_correta_cria(self, client, chave_admin):
        resp = client.post("/eventos", json=self.payload, headers=chave_admin)
        assert resp.status_code == 201

    def test_admin_api_key_legado_aceita(self, client, monkeypatch):
        """ADMIN_API_KEY (ADRs 0001/0002) continua válido como fallback."""
        monkeypatch.delenv("EVENTREG_API_KEY", raising=False)
        monkeypatch.setenv("ADMIN_API_KEY", "legada")
        resp = client.post(
            "/eventos", json=self.payload, headers={"X-Admin-Key": "legada"}
        )
        assert resp.status_code == 201


class TestOrigemInscricao:
    """Inscrição pública rejeita Origin de outro host (cross-site)."""

    def test_origem_externa_negada(self, client, evento_com_inscricao):
        resp = client.post(
            f"/eventos/{evento_com_inscricao}/inscricoes",
            json={"nome": "Ataque", "email": "ataque@mal.example"},
            headers={"Origin": "https://malicioso.example"},
        )
        assert resp.status_code == 403

    def test_origem_mesma_permitida(self, client, evento_com_inscricao):
        resp = client.post(
            f"/eventos/{evento_com_inscricao}/inscricoes",
            json={"nome": "Ok", "email": "ok@email.com"},
            headers={"Origin": "http://localhost"},
        )
        assert resp.status_code == 201

    def test_sem_origem_permitida(self, client, evento_com_inscricao):
        """Clientes sem Origin (curl, aplicativos) continuam permitidos."""
        resp = client.post(
            f"/eventos/{evento_com_inscricao}/inscricoes",
            json={"nome": "Curl", "email": "curl@email.com"},
        )
        assert resp.status_code == 201


class TestIdsAleatorios:
    """IDs públicos são UUIDv4, não sequenciais (anti-enumeração)."""

    def test_id_evento_e_uuid(self, client, chave_admin):
        resp = client.post(
            "/eventos",
            json={"nome": "W", "data": "2026-06-20", "capacidade_maxima": 5},
            headers=chave_admin,
        )
        assert resp.status_code == 201
        uuid.UUID(resp.get_json()["id"])  # inválido lançaria ValueError

    def test_id_participante_e_uuid(self, client, evento_com_inscricao):
        resp = client.post(
            f"/eventos/{evento_com_inscricao}/inscricoes",
            json={"nome": "Luann", "email": "luann2@email.com"},
        )
        assert resp.status_code == 201
        uuid.UUID(resp.get_json()["participante"]["id"])

    def test_ids_nao_sao_sequenciais(self, client, chave_admin):
        ids = []
        for _ in range(2):
            resp = client.post(
                "/eventos",
                json={"nome": "W", "data": "2026-06-20", "capacidade_maxima": 5},
                headers=chave_admin,
            )
            ids.append(resp.get_json()["id"])
        assert ids[0] != ids[1]
        assert not (ids[0].isdigit() and ids[1].isdigit())


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
