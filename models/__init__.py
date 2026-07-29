"""
Models — representacao de dados do CRIS OS.
Usados como estrutura de dados entre repositories e services.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Conversa:
    usuario_id: str
    papel: str
    conteudo: str
    agente: Optional[str] = None
    id: Optional[int] = None
    criado_em: Optional[str] = None


@dataclass
class Preferencia:
    usuario_id: str
    chave: str
    valor: str
    id: Optional[int] = None


@dataclass
class Cliente:
    usuario_id: str
    nome: str
    empresa: str = ""
    telefone: str = ""
    email: str = ""
    observacoes: str = ""
    id: Optional[int] = None
    criado_em: Optional[str] = None
    atualizado_em: Optional[str] = None


@dataclass
class Projeto:
    usuario_id: str
    nome: str
    descricao: str = ""
    status: str = "ativo"
    contexto: str = ""
    id: Optional[int] = None
    criado_em: Optional[str] = None
    atualizado_em: Optional[str] = None


@dataclass
class Tarefa:
    usuario_id: str
    titulo: str
    descricao: str = ""
    prioridade: str = "media"
    prazo: str = ""
    responsavel: str = ""
    status: str = "pendente"
    projeto_id: Optional[int] = None
    id: Optional[int] = None
    criado_em: Optional[str] = None
    atualizado_em: Optional[str] = None


@dataclass
class Prompt:
    usuario_id: str
    titulo: str
    conteudo: str
    categoria: str = ""
    favorito: bool = False
    id: Optional[int] = None
    criado_em: Optional[str] = None


@dataclass
class Configuracao:
    usuario_id: str
    chave: str
    valor: str
    id: Optional[int] = None


@dataclass
class LogAtividade:
    usuario_id: str = ""
    agente: str = ""
    ferramenta: str = ""
    modelo: str = ""
    duracao_ms: int = 0
    erro: str = ""
    id: Optional[int] = None
    criado_em: Optional[str] = None
