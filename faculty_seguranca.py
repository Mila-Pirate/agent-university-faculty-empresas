from fastmcp import FastMCP
from fastmcp.server.context import Context
import requests
import os

mcp = FastMCP("Agent University - Faculty of Public Safety")

def _normalize_text(text: str) -> str:
    """Normalizza il testo per l'API (maiuscolo, spazi)."""
    return text.strip().upper().replace(" ", "+")

@mcp.tool()
async def avaliar_risco_criminal_por_cep(cep: str, ctx: Context) -> dict:
    """
    Avalia o risco criminal de um CEP brasileiro.
    Retorna um índice de risco (Alto/Medio/Basso), taxa por 100k habitantes,
    e os tipos de crime mais comuns na região.
    """
    # 1. Valida e limpa o CEP
    cep_limpo = ''.join(filter(str.isdigit, cep))
    if len(cep_limpo) != 8:
        return {"erro": "CEP inválido. Deve conter 8 dígitos."}

    # 2. Busca localidade via ViaCEP (gratuito, sem chave)
    try:
        viacep_url = f"https://viacep.com.br/ws/{cep_limpo}/json/"
        resp = requests.get(viacep_url, timeout=10)
        resp.raise_for_status()
        endereco = resp.json()
        if "erro" in endereco:
            return {"erro": "CEP não encontrado no ViaCEP."}
    except Exception as e:
        return {"erro": f"Falha ao consultar ViaCEP: {str(e)}"}

    municipio = endereco.get("localidade")
    uf = endereco.get("uf")
    bairro = endereco.get("bairro")

    # 3. Consulta Crime Brasil
    try:
        # Monta a URL com os parâmetros
        base_url = "https://crimebrasil.com.br/api/location-stats"
        params = {
            "state": uf,
            "municipio": _normalize_text(municipio),
            "ultimos_meses": 12
        }
        if bairro:
            params["bairro"] = _normalize_text(bairro)

        resp_crime = requests.get(base_url, params=params, timeout=15)
        
        # Se a API retornar 404 ou erro, tentamos sem o bairro (fallback municipal)
        if resp_crime.status_code != 200 and bairro:
            params.pop("bairro")
            resp_crime = requests.get(base_url, params=params, timeout=15)
        
        resp_crime.raise_for_status()
        dados = resp_crime.json()
        
    except Exception as e:
        return {"erro": f"Falha ao consultar Crime Brasil: {str(e)}"}

    # 4. Calcula o índice de risco
    total = dados.get("total", 0)
    populacao = dados.get("population", 1)
    
    if populacao == 0:
        return {"erro": "População não disponível para esta localidade."}

    # Taxa por 100k habitantes
    taxa_100k = (total / populacao) * 100000

    # Define o índice (soglia baseada em médias nacionais aproximadas)
    # Isso é uma heurística inicial, que pode ser refinada depois.
    if taxa_100k > 5000:
        risco = "Alto"
    elif taxa_100k > 2000:
        risco = "Médio"
    else:
        risco = "Baixo"

    # 5. Estrutura a resposta
    return {
        "cep": cep_limpo,
        "localidade": {
            "municipio": municipio,
            "uf": uf,
            "bairro": bairro,
            "populacao": populacao,
            "fonte_populacao": dados.get("population_source")
        },
        "periodo": "Últimos 12 meses",
        "total_crimes": total,
        "taxa_por_100k_habitantes": round(taxa_100k, 2),
        "indice_risco": risco,
        "tipos_de_crime_mais_comuns": dados.get("crime_types", [])[:5],  # Top 5
        "nota": "Dados agregados. O nível de detalhe (bairro vs. município) depende da fonte oficial."
    }

@mcp.tool()
def listar_atividades_disponiveis() -> list:
    """Lista as atividades disponíveis nesta faculdade."""
    return [
        {"categoria": "seguranca", "descricao": "Avaliação de risco criminal por CEP"},
    ]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="http", host="0.0.0.0", port=port, stateless_http=True)
