import os
import csv
import io
import requests
import uvicorn
from fastmcp import FastMCP
from fastmcp.server.context import Context
from apipj import Apipj, cnpj_valido, normalizar_cnpj
from paymcp import Mode, price, PayMCP
from paymcp.providers import X402Provider
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route, Mount

# --- CONFIGURAZIONE PAYMCP (CORRETTA) ---
wallet_address = os.getenv("VAULLS_PAY_TO")
if not wallet_address:
    raise ValueError("Wallet address non configurato. Imposta VAULLS_PAY_TO su Render.")

mcp = FastMCP("Agent University - Faculty of Brazilian Companies")

# Inizializza PayMCP con il Facilitator per la verifica crittografica
PayMCP(
    mcp,
    providers=[
        X402Provider(
            pay_to=[{"address": wallet_address}],
            # Usa 'facilitator' (non 'facilitator_url')
            facilitator={"url": "https://x402.org/facilitator"}
        )
    ],
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
        
        socios_list = []
        for s in empresa.get("socios", []):
            socios_list.append({
                "nome": str(s.get("nome", "")).encode('utf-8', errors='ignore').decode('utf-8'),
                "qualificacao": s.get("qualificacao")
            })
        
        return {
            "dado": {
                "cnpj": empresa.get("cnpj"),
                "razao_social": str(empresa.get("razao_social", "")).encode('utf-8', errors='ignore').decode('utf-8'),
                "nome_fantasia": str(empresa.get("nome_fantasia", "")).encode('utf-8', errors='ignore').decode('utf-8'),
                "situacao_cadastral": empresa.get("situacao_cadastral", {}).get("descricao"),
                "data_inicio_atividade": empresa.get("data_inicio_atividade"),
                "endereco": {
                    "logradouro": str(empresa.get("endereco", {}).get("logradouro", "")).encode('utf-8', errors='ignore').decode('utf-8'),
                    "numero": empresa.get("endereco", {}).get("numero"),
                    "municipio": str(empresa.get("endereco", {}).get("municipio", {}).get("nome", "")).encode('utf-8', errors='ignore').decode('utf-8'),
                    "uf": empresa.get("endereco", {}).get("uf"),
                    "cep": empresa.get("endereco", {}).get("cep")
                },
                "atividade_principal": str(empresa.get("cnae_principal", {}).get("descricao", "")).encode('utf-8', errors='ignore').decode('utf-8'),
                "capital_social": empresa.get("capital_social"),
                "socios": socios_list
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
CEIS_URL = "https://portaldatransparencia.gov.br/download-de-dados/ceis"

@mcp.tool()
@price(0.02, "USD")
async def verificar_sancoes_ceis(cnpj: str, ctx: Context) -> dict:
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj_limpo) != 14:
        return {"erro": "CNPJ inválido. Deve conter 14 dígitos."}
    
    try:
        response = requests.get(CEIS_URL, timeout=30)
        response.raise_for_status()
        reader = csv.DictReader(io.StringIO(response.text), delimiter=';')
        
        sancoes = []
        for row in reader:
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
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj_limpo) != 14:
        return {"erro": "CNPJ inválido. Deve conter 14 dígitos."}
    
    try:
        response = requests.get(CNEP_URL, timeout=30)
        response.raise_for_status()
        reader = csv.DictReader(io.StringIO(response.text), delimiter=';')
        
        sancoes = []
        for row in reader:
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
    """
    Lista os serviços disponíveis nesta universidade.
    Use esta ferramenta para descobrir qual ferramenta paga chamar para obter os dados.
    """
    return [
        {
            "categoria": "empresas",
            "descricao": "Consulta de CNPJ com proveniência certificada (Receita Federal).",
            "ferramenta_recomendada": "buscar_empresa_por_cnpj",
            "custo": "$0.01 USD por chamada",
            "quando_usar": "Use quando precisar de dados cadastrais básicos de uma empresa."
        },
        {
            "categoria": "compliance_ceis",
            "descricao": "Verificação de sanções no CEIS (CGU).",
            "ferramenta_recomendada": "verificar_sancoes_ceis",
            "custo": "$0.02 USD por chamada",
            "quando_usar": "Use quando precisar saber se uma empresa está impedida de contratar com o governo."
        },
        {
            "categoria": "compliance_cnep",
            "descricao": "Verificação de punições no CNEP (Lei Anticorrupção).",
            "ferramenta_recomendada": "verificar_sancoes_cnep",
            "custo": "$0.02 USD por chamada",
            "quando_usar": "Use quando precisar saber se uma empresa foi punida por corrupção."
        }
    ]

# --- DISCOVERY X402 (.well-known) ---
async def x402_discovery(request):
    wallet = os.getenv("VAULLS_PAY_TO")
    return JSONResponse({
        "name": "Agent University - Brazilian Company Data",
        "description": "Certified Brazilian CNPJ & sanctions data for AI agents.",
        "version": "1.5.0",
        "network": {"chainId": 8453, "currency": "USDC"},
        "payTo": wallet,
        "resources": [
            {
                "method": "POST",
                "path": "/mcp",
                "description": "MCP endpoint with tools: buscar_empresa_por_cnpj, verificar_sancoes_ceis, verificar_sancoes_cnep",
                "price": "variable"
            }
        ],
        "links": {"documentation": "https://github.com/Mila-Pirate/agent-university-empresas"}
    })

# ... (dopo la funzione x402_discovery e prima di mcp_app = ...) ...

# --- LLMS.TXT ---
async def llms_txt(request):
    content = """# Agent University - Brazilian Company Data

> Certified Brazilian company data and sanctions screening for AI agents. Pay-per-call via x402.

This server provides structured, certified data from official Brazilian government sources. Agents can verify company registration and screen for sanctions.

## Available Tools

- [CNPJ Lookup](https://agent-university-empresas.onrender.com/mcp): Get company registration data from Receita Federal.
- [CEIS Screening](https://agent-university-empresas.onrender.com/mcp): Check if a company is suspended from public contracts.
- [CNEP Screening](https://agent-university-empresas.onrender.com/mcp): Check for anti-corruption punishments.

## Documentation

- [GitHub Repository](https://github.com/Mila-Pirate/agent-university-empresas): Source code and full documentation.
"""
    return PlainTextResponse(content)

# --- AGENTS.JSON ---
async def agents_json(request):
    return JSONResponse({
        "version": "1.0",
        "name": "Agent University - Brazilian Company Data",
        "description": "Certified Brazilian company data and sanctions screening.",
        "skills": [
            {
                "id": "cnpj_lookup",
                "name": "CNPJ Lookup",
                "description": "Get company registration data from Receita Federal.",
                "endpoint": "https://agent-university-empresas.onrender.com/mcp",
                "method": "POST",
                "pricing": {"model": "per_call", "amount": "0.01", "currency": "USD"}
            },
            {
                "id": "ceis_screening",
                "name": "CEIS Sanctions Screening",
                "description": "Check if a company is suspended from public contracts.",
                "endpoint": "https://agent-university-empresas.onrender.com/mcp",
                "method": "POST",
                "pricing": {"model": "per_call", "amount": "0.02", "currency": "USD"}
            },
            {
                "id": "cnep_screening",
                "name": "CNEP Sanctions Screening",
                "description": "Check for anti-corruption punishments.",
                "endpoint": "https://agent-university-empresas.onrender.com/mcp",
                "method": "POST",
                "pricing": {"model": "per_call", "amount": "0.02", "currency": "USD"}
            }
        ]
    })

# --- MCP SERVER CARD ---
async def mcp_server_card(request):
    return JSONResponse({
        "name": "agent-university-empresas",
        "description": "Certified Brazilian CNPJ & sanctions data for AI agents.",
        "version": "1.5.0",
        "author": "Mila-Pirate",
        "repository": "https://github.com/Mila-Pirate/agent-university-empresas",
        "tools": [
            {"name": "buscar_empresa_por_cnpj", "description": "Get company registration data from Receita Federal."},
            {"name": "verificar_sancoes_ceis", "description": "Check CEIS sanctions."},
            {"name": "verificar_sancoes_cnep", "description": "Check CNEP punishments."},
            {"name": "listar_atividades_disponiveis", "description": "List available tools and prices."}
        ],
        "categories": ["brazil", "compliance", "company-data", "sanctions"],
        "pricing": "paid",
        "auth_required": false,
        "transport": "http"
    })

# --- APP STARLETTE ---
mcp_app = mcp.http_app(transport="http", stateless_http=True)

app = Starlette(
    routes=[
        Route("/.well-known/x402", x402_discovery),
        Route("/llms.txt", llms_txt),
        Route("/agents.json", agents_json),
        Route("/.well-known/mcp/server-card.json", mcp_server_card),  # <-- ROUTE NORMALE
        Mount("/", app=mcp_app)
    ],
    lifespan=mcp_app.lifespan
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
