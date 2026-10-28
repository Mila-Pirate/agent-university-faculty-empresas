from fastmcp import FastMCP
from apipj import Apipj, cnpj_valido, normalizar_cnpj

# Inizializza il server MCP con il nome della tua Università
mcp = FastMCP("Agent University - Faculty of Brazilian Companies")

# Inizializza il client apipj
# Senza chiave usa la quota di test (3 req/min, 100/giorno)
# Per la quota gratuita completa (50.000/mese), crea un account su apipj.com.br/criar-conta
# ed esporta la chiave: export APIPJ_KEY=apipj_live_...
api = Apipj()

# --- STRUMENTO 1: Cerca un'azienda per CNPJ ---
@mcp.tool()
def buscar_empresa_por_cnpj(cnpj: str) -> dict:
    """
    Busca dados cadastrais de uma empresa brasileira pelo CNPJ.
    Retorna razão social, situação, endereço e sócios.
    """
    # Valida o CNPJ localmente (não gasta cota se inválido)
    if not cnpj_valido(cnpj):
        return {"erro": "CNPJ inválido. Verifique os dígitos."}
    
    try:
        empresa = api.consultar(normalizar_cnpj(cnpj))
        
        # Se a empresa não for encontrada (404), retorna erro estruturado
        if empresa is None:
            return {"erro": "CNPJ não encontrado na base da Receita Federal."}
        
        # Estrutura a resposta para o agente
        # Nota: apipj usa campos aninhados (endereco.municipio.nome, cnae_principal.descricao)
        return {
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
        }
    except Exception as e:
        return {"erro": f"Falha na consulta: {str(e)}"}

# --- STRUMENTO 2: Lista as atividades disponíveis na faculdade ---
@mcp.tool()
def listar_atividades_disponiveis() -> list:
    """
    Retorna uma lista de categorias de atividades para as quais a faculdade
    possui ferramentas de consulta (ex: 'empresas', 'contratos').
    """
    return [
        {"categoria": "empresas", "descricao": "Consulta de CNPJ e dados cadastrais"},
    ]

# --- Ponto di ingresso per test locale ---
if __name__ == "__main__":
    mcp.run()
