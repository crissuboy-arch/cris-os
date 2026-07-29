"""
PromptRepository — acesso a biblioteca de prompts no SQLite.
"""

from repositories.base import BaseRepository


class PromptRepository(BaseRepository):
    TABELA = "prompts_favoritos"
    COLUNAS = ("usuario_id", "titulo", "conteudo", "categoria", "favorito")

    def adicionar(self, usuario_id: str, titulo: str, conteudo: str,
                  categoria: str = "", favorito: bool = False) -> int:
        return self.insert(
            usuario_id=usuario_id, titulo=titulo, conteudo=conteudo,
            categoria=categoria, favorito=int(favorito),
        )

    def favoritos(self, usuario_id: str) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? AND favorito=1 "
            f"ORDER BY criado_em DESC",
            (usuario_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def buscar(self, usuario_id: str, termo: str) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? AND "
            f"(titulo LIKE ? OR conteudo LIKE ? OR categoria LIKE ?)",
            (usuario_id, f"%{termo}%", f"%{termo}%", f"%{termo}%"),
        )
        return [dict(r) for r in cur.fetchall()]

    def por_categoria(self, usuario_id: str, categoria: str) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? AND categoria=? "
            f"ORDER BY criado_em DESC",
            (usuario_id, categoria),
        )
        return [dict(r) for r in cur.fetchall()]

    def alternar_favorito(self, id: int) -> bool:
        row = self.get_by_id(id)
        if not row:
            return False
        novo = 0 if row["favorito"] else 1
        return self.update(id, favorito=novo)
