# RaydiumAPYScraper

A prototype of scraping APY data of farms and LPs on Raydium with async I/O.

Only necessary Solana API calls that are relevant to APY scraping were rewritten in async version.

Fee APR and token price were retrieved from Raydium API endpoint (api.raydium.io).

The output includes:

1. LP share supply and LP share price.
2. Token price.
3. The amount of each token in the LP, i.e. LP composition.
4. Liquidity value.
5. Staking LP APR.
6. Fee APR (i.e. 1 Yr Fee / Liquidity).

Feedback is welcomed.
