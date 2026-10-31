import os
import csv
import io
import requests
from fastmcp import FastMCP
from fastmcp.server.context import Context
from apipj import Apipj, cnpj_valido, normalizar_cnpj
from paymcp import Mode, price, PayMCP
from paymcp.providers import X402Provider

# --- CONFIGURAZIONE PAYMCP ---
wallet_address = os.getenv("VAULLS_PAY_TO")
if not wallet_address:
    raise ValueError("Wallet address non configurato. Imposta VAULLS_PAY_TO su Render.")

mcp = FastMCP("Agent University - Faculty of Brazilian Companies")

PayMCP(
    mcp,
    providers=[X402Provider(pay_to=[{"address": wallet_address}])],
    mode=Mode.X402
)

# --- CORSO 1: DATI AZIENDALI ---
@mcp.tool()
@price(0.01, "USD")
async def buscar_empresa_por_cnpj(cnpj: str, ctx: Context) -> dict:
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

# --- CORSO 2: SCREENING SANZIONI (CEIS) ---
# URL del file CSV pubblico del CEIS (Portal da Transparência)
CEIS_URL = "https://portaldatransparencia.gov.br/download-de-dados/ceis"

@mcp.tool()
@price(0.02, "USD")
async def verificar_sancoes_ceis(cnpj: str, ctx: Context) -> dict:
    """
    Verifica se un'azienda (CNPJ) è sanzionata nel CEIS.
    Scarica il file CSV pubblico e cerca il CNPJ.
    """
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj_limpo) != 14:
        return {"erro": "CNPJ inválido. Deve conter 14 dígitos."}
    
    try:
        # Scarica il CSV (il file è pubblico, non richiede chiave)
        # Nota: il download è pesante (decine di MB), quindi lo facciamo in memoria.
        response = requests.get(CEIS_URL, timeout=30)
        response.raise_for_status()
        
        # Legge il CSV
        # Il separatore è il punto e virgola (;)
        reader = csv.DictReader(io.StringIO(response.text), delimiter=';')
        
        sancoes = []
        for row in reader:
            # La colonna del CNPJ potrebbe chiamarsi "CPF/CNPJ do Sancionado"
            cnpj_sancionado = row.get("CPF/CNPJ do Sancionado", "")
            if cnpj_limpo in cnpj_sancionado:
                sancoes.append({
                    "tipo_sancao": row.get("Tipo de Sanção"),
                    "orgao_sancionador": row.get("Órgão Sancionador"),
                    "data_publicacao": row.get("Data Publicação"),
                    "data_fim": row.get("Data Final"),
                    "valor_multa": row.get("Valor da Multa")
                })
        
        return {
            "dado": {
                "cnpj": cnpj_limpo,
                "sancionada": len(sancoes) > 0,
                "total_sancoes": len(sancoes),
                "sancoes": sancoes
            },
            "provenienza": {
                "fonte_primaria": "CGU - Portal da Transparência (CEIS)",
                "livello_certificazione": "L1 - Fonte governativa oficial",
                "nota": "Dados extraídos do arquivo CSV público e filtrados por CNPJ."
            }
        }
    except Exception as e:
        return {"erro": f"Falha na consulta CEIS: {str(e)}"}

# --- CORSO 3: SCREENING SANZIONI (CNEP) ---
CNEP_URL = "https://portaldatransparencia.gov.br/download-de-dados/cnep"

@mcp.tool()
@price(0.02, "USD")
async def verificar_sancoes_cnep(cnpj: str, ctx: Context) -> dict:
    """
    Verifica se un'azienda (CNPJ) è punita nel CNEP (Cadastro Nacional de Empresas Punidas).
    Usa il file CSV pubblico, senza bisogno di chiave API.
    """
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj_limpo) != 14:
        return {"erro": "CNPJ inválido. Deve conter 14 dígitos."}
    
    try:
        # Scarica il CSV pubblico del CNEP
        response = requests.get(CNEP_URL, timeout=30)
        response.raise_for_status()
        
        reader = csv.DictReader(io.StringIO(response.text), delimiter=';')
        
        sancoes = []
        for row in reader:
            # La colonna del CNPJ nel CNEP si chiama "CPF/CNPJ do Sancionado"
            cnpj_sancionado = row.get("CPF/CNPJ do Sancionado", "")
            if cnpj_limpo in cnpj_sancionado:
                sancoes.append({
                    "tipo_sancao": row.get("Tipo de Sanção"),
                    "orgao_sancionador": row.get("Órgão Sancionador"),
                    "data_publicacao": row.get("Data Publicação"),
                    "data_fim": row.get("Data Final"),
                    "valor_multa": row.get("Valor da Multa")
                })
        
        return {
            "dado": {
                "cnpj": cnpj_limpo,
                "sancionada": len(sancoes) > 0,
                "total_sancoes": len(sancoes),
                "sancoes": sancoes
            },
            "provenienza": {
                "fonte_primaria": "CGU - Portal da Transparência (CNEP)",
                "livello_certificazione": "L1 - Fonte governativa oficial",
                "nota": "Dados extraídos do arquivo CSV público e filtrados por CNPJ."
            }
        }
    except Exception as e:
        return {"erro": f"Falha na consulta CNEP: {str(e)}"}
    
# --- TOOL GRATUITO: SCOPERTA ---
@mcp.tool()
def listar_atividades_disponiveis() -> list:
    return [
        {"categoria": "empresas", "descricao": "Consulta de CNPJ com proveniência certificada"},
        {"categoria": "compliance", "descricao": "Verificação de sanções (CEIS e CNEP)"}
    ]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="http", host="0.0.0.0", port=port, stateless_http=True)
