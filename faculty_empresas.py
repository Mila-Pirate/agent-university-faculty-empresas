import os
from fastmcp import FastMCP
from fastmcp.server.context import Context
from apipj import Apipj, cnpj_valido, normalizar_cnpj

# --- CONFIGURAZIONE PAYWALL (VAULLS) ---
# Sostituisci l'indirizzo con quello del tuo wallet MetaMask (rete Base)
try:
    from vaulls import configure, paywall
    configure(pay_to=os.getenv("VAULLS_PAY_TO", "0x35d5Cf139401F99C3788c488F438Dfdf035Ff50C"))
    PAYWALL_ACTIVE = True
except ImportError:
    # Se VAULLS non è installato (es. in locale senza paywall), il server funziona lo stesso
    PAYWALL_ACTIVE = False
    def paywall(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Inizializza il server MCP con il nome della tua Università
mcp = FastMCP("Agent University - Faculty of Brazilian Companies")

# --- STRUMENTO 1: Cerca un'azienda per CNPJ (CON PAYWALL) ---
@paywall(price="0.01", description="Dati CNPJ con provenienza verificata")
@mcp.tool()
async def buscar_empresa_por_cnpj(cnpj: str, ctx: Context) -> dict:
    """
    Busca dados cadastrais de uma empresa brasileira pelo CNPJ.
    Retorna razão social, situação, endereço e sócios.
    """
    # Legge la chiave dall'header X-Apipj-Key, o dalla variabile d'ambiente
    api_key = None
    try:
        api_key = ctx.request_context.request.headers.get("x-apipj-key")
    except Exception:
        pass
    if not api_key:
        api_key = os.getenv("APIPJ_KEY")
    
    if not api_key:
        return {"erro": "Chave API apipj não configurada. Envie o header X-Apipj-Key ou configure APIPJ_KEY."}
    
    api = Apipj(chave=api_key, avisos=False)
    
    if not cnpj_valido(cnpj):
        return {"erro": "CNPJ inválido. Verifique os dígitos."}
    
    try:
        empresa = api.consultar(normalizar_cnpj(cnpj))
        if empresa is None:
            return {"erro": "CNPJ não encontrado na base da Receita Federal."}
        
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
                "socios": [
                    {"nome": s.get("nome"), "qualificacao": s.get("qualificacao")}
                    for s in empresa.get("socios", [])
                ]
            },
            "provenienza": {
                "fonte_primaria": "Receita Federal do Brasil (via apipj)",
                "timestamp_estrazione": "Dinâmico (consultado em tempo real)",
                "livello_certificazione": "L2 - Fonte governativa ufficiale + parsing",
                "nota": "Dados estruturados e validados. Ideal para compliance e due diligence."
            }
        }
    except Exception as e:
        return {"erro": f"Falha na consulta: {str(e)}"}

# --- STRUMENTO 2: Lista as atividades disponíveis na faculdade (GRATUITO) ---
@mcp.tool()
def listar_atividades_disponiveis() -> list:
    """
    Retorna uma lista de categorias de atividades para as quais a faculdade
    possui ferramentas de consulta.
    """
    return [
        {"categoria": "empresas", "descricao": "Consulta de CNPJ e dados cadastrais com proveniência certificada"},
    ]

# --- Ponto di ingresso per il server ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="http", host="0.0.0.0", port=port, stateless_http=True)
