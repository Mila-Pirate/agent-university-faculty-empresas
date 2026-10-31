# Agent University - Brazilian Company Data

Certified Brazilian company data and sanctions screening for AI agents. Pay-per-call via x402. No subscriptions, no API keys.

## What This Server Provides

This MCP server exposes two certified tools for AI agents performing compliance, due diligence, or procurement tasks in Brazil:

1. **`buscar_empresa_por_cnpj`** ($0.01 USD per call)
   - Returns structured company registration data (CNPJ) from the Brazilian Federal Revenue.
   - Includes: legal name, status, address, partners, and economic activity.
   - Provenance: L2 (official government source + structured parsing).

2. **`verificar_sancoes_ceis`** ($0.02 USD per call)
   - Screens a CNPJ against the CEIS (List of Suspended/Ineligible Companies) from the Brazilian Office of the Comptroller General (CGU).
   - Returns: sanction status, details of any sanctions found.
   - Provenance: L1 (official government source).

## How Agents Pay

This server uses the **x402 protocol** for per-call settlement in **USDC on Base** (eip155:8453). Agents pay only for successful calls. No subscriptions, no seats, no invoices.

The server returns a `402 Payment Required` response with the payment details. Any x402-compatible client (CDP SDK, x402-fetch, agent-tools-mcp) can resolve the payment automatically.

## MCP Endpoint

`https://agent-university-empresas.onrender.com/mcp` (Streamable HTTP)

## Discovery Metadata

- Registry: `io.github.Mila-Pirate/agent-university-empresas`
- Version: 1.3.0
- x402 Network: Base Mainnet (`eip155:8453`)
- Payment Asset: USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)

## License

MIT
