import os
from fastmcp import FastMCP
from fastmcp.server.context import Context
from apipj import Apipj, cnpj_valido, normalizar_cnpj
from vaulls import configure, paywall
from vaulls.integrations.fastapi import vaulls_middleware
import uvicorn

# --- CONFIGURAZIONE VAULLS ---
# Legge il wallet dalla variabile d'ambiente VAULLS_PAY_TO (configurata su Render)
configure(pay_to=os.getenv("VAULLS_PAY_TO"))

mcp = FastMCP("Agent University - Faculty of Brazilian Companies")

# --- STRUMENTO 1: Cerca un'azienda per CNPJ (CON PAYWALL) ---
@mcp.tool()
@paywall(price="0.01", description="Dados de CNPJ com proveniência certificada")
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

# --- STRUMENTO 2: Lista attività (GRATUITO, per scoperta) ---
@mcp.tool()
def listar_atividades_disponiveis() -> list:
    return [{"categoria": "empresas", "descricao": "Consulta de CNPJ com proveniência certificada"}]

# --- AVVIO CON MIDDLEWARE VAULLS ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Crea l'app ASGI di FastMCP e la avvolge con il middleware VAULLS
    app = mcp.http_app(transport="http", stateless_http=True)
    app = vaulls_middleware(app)
    uvicorn.run(app, host="0.0.0.0", port=port)
