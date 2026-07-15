"""
Script de validação rápida da integração com NVIDIA AI.

Uso:
    python scripts/test_nvidia.py

Requer NVIDIA_API_KEY preenchida no .env.
"""

import sys
import os
from pathlib import Path

from dotenv import load_dotenv

# Garante que o diretório raiz do projeto está no sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")

from llm.nvidia import NVIDIAProvider, NVIDIAError


def main():
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct").strip()

    if not api_key or api_key == "COLE_SUA_CHAVE_AQUI":
        print("ERRO: NVIDIA_API_KEY nao preenchida no .env")
        sys.exit(1)

    print(f"Conectando a NVIDIA via {base_url}")
    print(f"Modelo: {model}")
    print()

    provider = NVIDIAProvider(
        api_key=api_key,
        model=model,
        base_url=base_url,
    )

    if not provider.is_alive():
        print("ERRO: NVIDIA nao esta acessivel. Verifique sua chave e conexao.")
        sys.exit(1)

    print("NVIDIA esta acessivel. Enviando mensagem de teste...\n")

    try:
        resposta = provider.chat([
            {"role": "user", "content": "Responda apenas: NVIDIA funcionando."},
        ])
    except NVIDIAError as e:
        print(f"ERRO: {e}")
        sys.exit(1)

    print("=" * 50)
    print("RESPOSTA DA NVIDIA:")
    print(resposta.content if resposta.content else "(vazia)")
    print("=" * 50)

    if "funcionando" in resposta.content.lower():
        print("\n Integracao NVIDIA validada com sucesso!")
    else:
        print("\nA resposta nao conteve a confirmacao esperada, mas a conexao funciona.")


if __name__ == "__main__":
    main()
