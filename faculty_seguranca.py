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
    cep_limpo = ''.join(filter(str.isdigit, cep))
    if len(cep_limpo) != 8:
        return {"erro": "CEP inválido. Deve conter 8 dígitos."}

    ibge_code = None
    municipio = None
    uf = None
    bairro = None

    # 1. BrasilAPI: obtém endereço E código IBGE
    try:
        brasilapi_url = f"https://brasilapi.com.br/api/cep/v1/{cep_limpo}"
        resp = requests.get(brasilapi_url, timeout=10)
        if resp.status_code == 200:
            endereco = resp.json()
            municipio = endereco.get("city")
            uf = endereco.get("state")
            bairro = endereco.get("neighborhood")
            ibge_obj = endereco.get("ibge")
            if isinstance(ibge_obj, dict):
                ibge_code = ibge_obj.get("city")
    except Exception:
        pass

    # Fallback: ViaCEP se BrasilAPI fallisce
    if not ibge_code:
        try:
            viacep_url = f"https://viacep.com.br/ws/{cep_limpo}/json/"
            resp = requests.get(viacep_url, timeout=10)
            resp.raise_for_status()
            endereco = resp.json()
            if "erro" not in endereco:
                municipio = endereco.get("localidade")
                uf = endereco.get("uf")
                bairro = endereco.get("bairro")
                ibge_code = endereco.get("ibge")
        except Exception:
            pass

    if not municipio or not uf:
        return {"erro": "CEP não encontrado."}

    # 2. Crime Brasil (con fallback da bairro a comune)
    try:
        base_url = "https://crimebrasil.com.br/api/location-stats"
        params = {
            "state": uf,
            "municipio": _normalize_text(municipio),
            "ultimos_meses": 12
        }
        if bairro:
            params["bairro"] = _normalize_text(bairro)

        resp_crime = requests.get(base_url, params=params, timeout=15)
        resp_crime.raise_for_status()
        dados = resp_crime.json()

        # Se il bairro non ha dati (total = 0), riprova senza bairro
        if bairro and dados.get("total", 0) == 0:
            params.pop("bairro", None)
            resp_crime = requests.get(base_url, params=params, timeout=15)
            resp_crime.raise_for_status()
            dados = resp_crime.json()
    except Exception as e:
        return {"erro": f"Falha ao consultar Crime Brasil: {str(e)}"}

    total = dados.get("total", 0)

    # 3. População: usa a API SIDRA do IBGE (mais simples e confiável)
    populacao = None
    if ibge_code:
        try:
            sidra_url = (
                f"https://apisidra.ibge.gov.br/values/t/10211/n6/{ibge_code}/v/93/p/2022"
            )
            resp_sidra = requests.get(sidra_url, timeout=15)
            if resp_sidra.status_code == 200:
                sidra_data = resp_sidra.json()
                if len(sidra_data) > 1:
                    linha_dados = sidra_data[1]
                    valor_str = linha_dados.get("V")
                    if valor_str and valor_str not in ("-", "..", "..."):
                        populacao = int(valor_str)
        except Exception:
            pass

    # Fallback: popolazione dal Crime Brasil
    if not populacao:
        populacao = dados.get("population")

    if not populacao or populacao == 0:
        return {"erro": "População não disponível para esta localidade. Tente outro CEP."}

    # 4. Índice de risco
    taxa_100k = (total / populacao) * 100000
    if taxa_100k > 5000:
        risco = "Alto"
    elif taxa_100k > 2000:
        risco = "Médio"
    else:
        risco = "Baixo"

    return {
        "cep": cep_limpo,
        "localidade": {
            "municipio": municipio,
            "uf": uf,
            "bairro": bairro,
            "populacao": populacao,
            "fonte_populacao": "IBGE Censo 2022" if ibge_code else dados.get("population_source")
        },
        "periodo": "Últimos 12 meses",
        "total_crimes": total,
        "taxa_por_100k_habitantes": round(taxa_100k, 2),
        "indice_risco": risco,
        "tipos_de_crime_mais_comuns": dados.get("crime_types", [])[:5],
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
