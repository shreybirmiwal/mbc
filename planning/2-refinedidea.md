

# product
0. records your day to day, always listening to audio
1. whenver hears smth it can find on polymarket it auto bets on polymarket

 a) "It's so hot outside" → Bet YES on "2024 will be the hottest year on record."
 b) "This debate is boring" → Bet NO on "Trump/Harris viewership numbers."
 c) "I'm never getting a girlfriend" → Bet YES on "Birth rates drop in 2025."

 Sends in the groupchat using mac macros
2. whenver it hears smth that is personal, like "im never getting a girlfriend" it creates a new market on solana or base, it will send it to the groupchat using mac imessage macro for ur friends to bet on it

2. BONUS W CAMERA if time: whenver it sees a new environment it takes picture, like if:
 a) with a girl: it creates new market "is xyz gonna get a kiss today" and sends it to the groupchat using mac imessage macro for ur friends to bet on it
 b) in front of big stage "is xyz gonna ace his presentaton"


# execution
0. Use iphone cmaera and mic (will be too complex / unlikely to work w ESP 32) taped to chest
1. listen all audio

react web app with
1 - client button on main frontend leads into secret page (this will be running on the iphone for the demo) that just records audio and gets words from it and sends to backend 
2 - backend server takes words, calls a few apis to get all markets, llms to get which markets applicable, bets on polymarket if applicable
*3 - backend creates custom markets on SOLANA OR BASE using USDC on circle
 ---> maybe just simple smart contract that u can take yes or no side from and it has title yk
4 - backend sends to groupchat using mac imessage macro that market was created or bet was created
5 - frontend shows all markets and bets / positions created on main page. cool ui displays all positions coming in and the quote the person said to prompt it

wow factor after:
 - create glasses that record everything instead of iphone
 - create camera with glasses


# bounties hackathon
either solana or base track (whichever is easier for the custom markets smart contract stuff)

## solana overview
We’re looking for a team to create a next onchain app that will onboard millions
using the best-in-class UX that Solana provides. Any project submission that is built
using Solana’s high performance infrastructure will be considered. Projects will be
judged on their innovation, technical skill, and impact on someone's everyday life.
Objectives
Projects should aim to:
Leverage Solana’s scalability, composability, and cost eﬃciency.
Solve practical problems for users and/or developers.
Demonstrate fluency with Solana’s SDKs, frameworks, and standards.
Showcase creativity, originality, and strong technical execution.
Technical Requirements
Projects must:
Deploy to or interact with Solana devnet or mainnet.
Use at least one Solana development tool or framework:
Anchor Framework (Rust)
Solana client sdks (@solana/web3.js, solanapy, @solana/kit, etc)
Include a public GitHub repository with documentation and setup
instructions.
Provide a functional demo (frontend or CLI-based).


## base overview
Overview
The Base Track is for projects built on Base’s Ethereum L2. With low fees, fast
finality, and full EVM compatibility, Base enables accessible onchain applications
that can scale to millions of users.
We’re looking for projects that show strong technical execution, originality, and clear
impact using Base’s infrastructure and ecosystem tools.
Objectives
Projects should aim to:
Build experiences that make onchain interactions simple, social, and engaging
Show clear utility, originality, and solid technical depth
Leverage Base’s infra and developer tooling effectively
Technical Requirements
Build on Base
Projects must deploy to, or meaningfully interact with:
Base Mainnet, or
Base Sepolia
Optional (Bonus) Integrations
Not required, but viewed favorably:
Base SDK / OnchainKit / MiniKit
Smart wallets, paymasters, ERC-4337 account abstraction
AgentKit or x402
Onchain data APIs (BaseScan, Dune, Reservoir, etc.)


### Bounty: Prediction Markets sponsored by Polymarket
Prize: $5,000
Overview:
Polymarket is a decentralized prediction market platform built on the EVM
infrastructure. This bounty rewards teams that integrate prediction market data,
build analytics tools, or design new market primitives that expand prediction-based
applications.
Objectives:
Create new on-chain market mechanisms or visualizations for market
sentiment
Integrate Polymarket APIs or data feeds for analytics or decision-making tools
Build UX-enhancing layers (dashboards, APIs, bots) using Polymarket data
Requirements:
Must use Polymarket’s public APIs or smart contract interfaces
May be built on Solana or Base (data integrations allowed cross-chain)
Projects must demonstrate clear utility and originality in prediction markets
October 7th 2025

### Bounty: USDC and Payments sponsored by Circle
Prize: $5,000
Overview:
Circle is the issuer of USDC, the leading dollar-backed stablecoin. This bounty is
open to teams creating new financial primitives or payment applications using USDC
across supported networks (including Solana and Base).
Objectives:
Build seamless cross-border or in-app payment experiences using USDC
Use Circle’s APIs for transfers, wallets, or merchant integrations
Innovate around treasury management, on-chain settlements, or
microtransactions
Requirements:   
Must integrate USDC on Solana or Base
Bonus points for using Circle developer APIs
Project demonstrates real-world relevance in payments/financial automation