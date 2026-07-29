"""
database — camada de persistencia do CRIS OS.

Fornece conexao SQLite e schema de todas as tabelas.
"""

from database.connection import get_connection, close_connection
from database.schema import criar_tabelas
