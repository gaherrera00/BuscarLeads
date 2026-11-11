"""Fila de avisos da camada de dados.

A camada de dados não pode depender do Streamlit (isso a tornava impossível
de testar sem abrir a interface). Quando algo merece atenção do usuário, ela
registra o aviso aqui e a interface mostra na próxima renderização.
"""

from __future__ import annotations

_fila: list[str] = []


def registrar(mensagem: str) -> None:
    if mensagem not in _fila:
        _fila.append(mensagem)


def consumir() -> list[str]:
    """Devolve os avisos pendentes e esvazia a fila."""
    pendentes = list(_fila)
    _fila.clear()
    return pendentes
