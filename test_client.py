# test_client.py
import asyncio
from fastmcp import Client

async def main():
    # Connessione al server locale (stdio)
    async with Client("faculty_empresas.py") as client:
        # 1. Elenca gli strumenti (l'agente "scopre" i corsi)
        tools = await client.list_tools()
        print("Strumenti disponibili:", [t.name for t in tools])

        # 2. Chiama lo strumento (l'agente "segue il corso")
        result = await client.call_tool("buscar_empresa_por_cnpj", {"cnpj": "00.000.000/0001-91"})
        print("Risultato:", result)

if __name__ == "__main__":
    asyncio.run(main())
