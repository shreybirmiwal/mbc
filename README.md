# Bazaar


### Table of Contents

<img width="1510" height="857" alt="Screenshot 2025-12-05 at 4 49 28 PM" src="https://github.com/user-attachments/assets/c82682c7-bda6-4e49-a7af-19c914893597" />

## Demo Video
https://www.youtube.com/watch?v=8rU6OIX4LAM

## Description
Bazaar tokenizes API pricing structures. Think BaseApp / Zora, but instead of each creator having a creator coin, each API having an API-Coin.

Each API is priced per usage according to the market value of its token. For example, using Gemini 3.0 may require spending a $GEM3 token, while Claude usage uses a $CLAUDE token. As token prices fluctuate based on demand, API costs automatically adjust—higher demand increases the cost, while lower demand decreases it.

By tokenizing API pricing structure, markets become flexible in pricing, increasing efficiency.
1. Devs can buy tokens, trade with other APIs, sell-off excess API credits, and take speculative positions on the future of API tokens
2. Self correcting price regulated by supply and demand keep firms and consumers producing/consuming at the optimal amount for minimum deadweight loss by optimizing the maximum social marginal utility

Bazaar works with x402 handling dynamic payments and flaunch handles token laucnhes and bonding curve mechanics. Flask backend manages the API metadata and interfaces the react frontend for trading and calling the APIs



## Technical Summary
Technical Summary
Problem Being Solved
API pricing is typically static, opaque, and disconnected from actual demand. Providers must guess rates, leading to inefficiencies, wasted resources, or overcharging users. Bazaar addresses this by creating market-driven pricing that adjusts dynamically based on real demand.
Layer 2 Advantages (Base)
Bazaar is deployed on Base to leverage low fees, fast transaction settlement, and seamless integration with crypto-native payment rails via x402. Base makes frequent token interactions, bonding-curve price updates, and API usage payments economically viable while ensuring smooth user experience.
EVM Stack Usage
Bazaar relies on existing EVM infrastructure rather than custom contracts. API tokens are launched via flaunch, which handles bonding-curve pricing, liquidity, and trading. Payments and API usage enforcement are handled through x402. This removes the need for custom smart contracts while still enabling on-chain settlement, tokenized API economies, and transparent market-driven pricing.
Off-Chain Components
The Flask backend manages API metadata, triggers flaunch token launches, and wraps APIs via x402. The React frontend provides a user-friendly interface for uploading APIs, viewing tokens, trading, and calling APIs. All heavy logic for pricing, token mechanics, and payment settlement is delegated to flaunch and x402.
Bazaar demonstrates how market mechanisms can be applied to API monetization, creating flexible, efficient, and transparent tokenized API economies without reinventing the on-chain stack.
