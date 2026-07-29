"""
ClienteRepository — acesso a clientes no SQLite.
"""

from repositories.base import BaseRepository


class ClienteRepository(BaseRepository):
    TABELA = "clientes"
    COLUNAS = ("usuario_id", "nome", "empresa", "telefone", "email", "observacoes")

    def criar(self, usuario_id: str, nome: str, empresa: str = "",
              telefone: str = "", email: str = "", observacoes: str = "") -> int:
        return self.insert(
            usuario_id=usuario_id, nome=nome, empresa=empresa,
            telefone=telefone, email=email, observacoes=observacoes,
        )

    def atualizar(self, id: int, **kwargs) -> bool:
        if "atualizado_em" not in kwargs:
            from datetime import datetime
            kwargs["atualizado_em"] = datetime.now().isoformat()
        return self.update(id, **kwargs)

    def buscar(self, usuario_id: str, termo: str) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? AND "
            f"(nome LIKE ? OR empresa LIKE ? OR telefone LIKE ? OR email LIKE ?)",
            (usuario_id, f"%{termo}%", f"%{termo}%", f"%{termo}%", f"%{termo}%"),
        )
        return [dict(r) for r in cur.fetchall()]
