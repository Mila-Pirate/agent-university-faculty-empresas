import os
from fastmcp import FastMCP
from fastmcp.server.context import Context
from apipj import Apipj, cnpj_valido, normalizar_cnpj
from paymcp import Mode, price, PayMCP
from paymcp.providers import X402Provider

# --- CONFIGURAZIONE PAYMCP ---
# Il wallet è quello che hai già impostato su Render come VAULLS_PAY_TO
wallet_address = os.getenv("VAULLS_PAY_TO") # riusa la variabile esistente
if not wallet_address:
    raise ValueError("Wallet address non configurato. Imposta VAULLS_PAY_TO su Render.")

mcp = FastMCP("Agent University - Faculty of Brazilian Companies")

# Inizializza PayMCP con il provider x402 (USDC su Base)
# Mode.X402 forza l'uso del protocollo x402 per i pagamenti on-chain
PayMCP(
    mcp,
    providers=[X402Provider(pay_to=[{"address": wallet_address}])],
    mode=Mode.X402
)

@mcp.tool()
@price(amount=0.01, currency="USD")
async def buscar_empresa_por_cnpj(cnpj: str, ctx: Context) -> dict:
    """
    Busca dados cadastrais de uma empresa brasileira pelo CNPJ.
    """
    api_key = os.getenv("APIPJ_KEY")
    if not api_key:
        return {"erro": "Chave API apipj não configurada no servidor."}
    
    api = Apipj(chave=api_key, avisos=False)
    
    if not cnpj_valido(cnpj):
        return {"erro": "CNPJ inválido."}
    
    try:
        empresa = api.consultar(normalizar_cnpj(cnpj))
        if empresa is None:
            return {"erro": "CNPJ não encontrado."}
        
        return {
            "dado": {
                "cnpj": empresa.get("cnpj"),
                "razao_social": empresa.get("razao_social"),
                "nome_fantasia": empresa.get("nome_fantasia"),
                "situacao_cadastral": empresa.get("situacao_cadastral", {}).get("descricao"),
                "data_inicio_atividade": empresa.get("data_inicio_atividade"),
                "endereco": {
                    "logradouro": empresa.get("endereco", {}).get("logradouro"),
                    "numero": empresa.get("endereco", {}).get("numero"),
                    "municipio": empresa.get("endereco", {}).get("municipio", {}).get("nome"),
                    "uf": empresa.get("endereco", {}).get("uf"),
                    "cep": empresa.get("endereco", {}).get("cep")
                },
                "atividade_principal": empresa.get("cnae_principal", {}).get("descricao"),
                "capital_social": empresa.get("capital_social"),
                "socios": [{"nome": s.get("nome"), "qualificacao": s.get("qualificacao")} for s in empresa.get("socios", [])]
            },
            "provenienza": {
                "fonte_primaria": "Receita Federal do Brasil (via apipj)",
                "livello_certificazione": "L2 - Fonte governativa ufficiale + parsing",
                "nota": "Dados estruturados e validados."
            }
        }
    except Exception as e:
        return {"erro": f"Falha na consulta: {str(e)}"}

@mcp.tool()
def listar_atividades_disponiveis() -> list:
    return [{"categoria": "empresas", "descricao": "Consulta de CNPJ com proveniência certificada"}]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="http", host="0.0.0.0", port=port, stateless_http=True)
