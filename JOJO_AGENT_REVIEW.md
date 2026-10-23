# JoJo agent ecosystem review

Snapshot: 2026-10-23. Source: [AI Agents ranking](https://github.com/yuxiaopeng/Github-Ranking-AI/blob/main/Top100/AI%20Agents.md).

## Scope and limitations

All 100 entries were indexed through GitHub metadata, pinned commit IDs, file trees and sampled README/license/source files. This is a breadth inventory, **not a complete manual audit of 100 codebases**, security certification, or integration of 100 agents. Some entries are collections, UI libraries or tutorials rather than executable agents. Representative files were fetched, not executed; automated sampling can select an example or retired component. No third-party install scripts ran and no vendor source was incorporated in this change.

The machine-readable `assets/jojo_agent_catalog.json` records sampled paths and commit IDs. License fields are GitHub metadata signals, not a determination that every component can be redistributed. Unknown, mixed-license and copyleft projects require separate review before reuse. Private research downloads are excluded from the source release.

## Implemented in JoJo

- Eight original, individually switchable workflow guides: debugging, research, browser interaction, document questions, memory, writing, planning and defensive review. Native Skills controls expose them. Matching English task keywords select at most two guides; the model can also request guidance explicitly. These are instructions for existing enabled tools, not eight new autonomous agents or model training. Non-English automatic matching remains limited.
- Large dictionary and text tool outputs now have an explicit bounded excerpt, original length, digest and partial-result warning. Small outputs retain their original structure. This bounds each result, not total conversation context; omitted content requires a narrower source query.
- Companion/professional/mentor/custom conversation styles, optional follow-up prompts and native settings. Voice and permissions remain separate.
- Direct laptop CPU/RAM/storage/battery status without a model round trip, with missing-sensor and single-sample caveats.

The selected technical patterns were informed by inspection of Hermes tool dispatch, Headroom memory tools, Mem0's Pi integration and Pi skill metadata/discovery. JoJo's existing permission checks, device binding, cancellation and evidence-based task completion remain in force. Features described by Stonic inspired the style/status controls; no private Stonic code was accessed or copied.

## Not implemented by this review

Wholesale framework replacement, arbitrary executable skill imports, model self-training, trading agents, network intrusion, automatic external account connections, and universal mobile/desktop operation. Tools still require their configured dependencies and permissions. Live model/device evaluation is separate from source regression tests.

## Repository inventory

| # | Repository | License signal | Pinned commit |
|---|---|---|---|
| 1 | [obra/superpowers](https://github.com/obra/superpowers) | MIT | `2ce8aa15d05b` |
| 2 | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | MIT | `db1fa153fe24` |
| 3 | [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) | AGPL-3.0 | `a779ddac4316` |
| 4 | [Significant-Gravitas/AutoGPT](https://github.com/Significant-Gravitas/AutoGPT) | NOASSERTION | `438b03d0ba93` |
| 5 | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | MIT | `09c434ab73ca` |
| 6 | [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | MIT | `4e3ac3ca6604` |
| 7 | [langgenius/dify](https://github.com/langgenius/dify) | NOASSERTION | `2b35144b2098` |
| 8 | [langflow-ai/langflow](https://github.com/langflow-ai/langflow) | MIT | `aeb10d96bb2e` |
| 9 | [langchain-ai/langchain](https://github.com/langchain-ai/langchain) | MIT | `3d3b0034a94e` |
| 10 | [x1xhlol/system-prompts-and-models-of-ai-tools](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools) | GPL-3.0 | `162db92f54d7` |
| 11 | [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) | Apache-2.0 | `6c16b23f1bac` |
| 12 | [browser-use/browser-use](https://github.com/browser-use/browser-use) | MIT | `3df5806a0d09` |
| 13 | [earendil-works/pi](https://github.com/earendil-works/pi) | MIT | `ede2c9b468d8` |
| 14 | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | Apache-2.0 | `b4531dfc05a3` |
| 15 | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | MIT | `aeac41d4d005` |
| 16 | [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) | Apache-2.0 | `a713410aba5d` |
| 17 | [nexu-io/open-design](https://github.com/nexu-io/open-design) | Apache-2.0 | `e03d5c23f308` |
| 18 | [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | Apache-2.0 | `dcb28a768c6b` |
| 19 | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | MIT | `6010f91a9935` |
| 20 | [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) | MIT | `beabda7486e9` |
| 21 | [karpathy/autoresearch](https://github.com/karpathy/autoresearch) | UNKNOWN | `228791fb499a` |
| 22 | [infiniflow/ragflow](https://github.com/infiniflow/ragflow) | Apache-2.0 | `a55dccee4c21` |
| 23 | [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | Apache-2.0 | `30165f1ee1fb` |
| 24 | [lobehub/lobehub](https://github.com/lobehub/lobehub) | NOASSERTION | `312ed3e5467e` |
| 25 | [dair-ai/Prompt-Engineering-Guide](https://github.com/dair-ai/Prompt-Engineering-Guide) | MIT | `57673726396d` |
| 26 | [ruvnet/ruflo](https://github.com/ruvnet/ruflo) | MIT | `88349655ebc2` |
| 27 | [microsoft/ai-agents-for-beginners](https://github.com/microsoft/ai-agents-for-beginners) | MIT | `735e18437e07` |
| 28 | [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | Apache-2.0 | `e995eb9f1dac` |
| 29 | [career-ops-hq/career-ops](https://github.com/career-ops-hq/career-ops) | MIT | `96a48ece9cd4` |
| 30 | [openbq-org/OpenBB](https://github.com/openbq-org/OpenBB) | NOASSERTION | `78020ee4b864` |
| 31 | [thedaviddias/Front-End-Checklist](https://github.com/thedaviddias/Front-End-Checklist) | MIT | `e8d14d049010` |
| 32 | [rohitg00/ai-engineering-from-scratch](https://github.com/rohitg00/ai-engineering-from-scratch) | MIT | `3f9715c62a3b` |
| 33 | [usestrix/strix](https://github.com/usestrix/strix) | Apache-2.0 | `14cc948c36e9` |
| 34 | [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage) | AGPL-3.0 | `c8066452325c` |
| 35 | [FoundationAgents/MetaGPT](https://github.com/FoundationAgents/MetaGPT) | MIT | `11cdf466d042` |
| 36 | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | Apache-2.0 | `bd4cae7e3582` |
| 37 | [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | MIT | `cefbfd67b6a0` |
| 38 | [mem0ai/mem0](https://github.com/mem0ai/mem0) | Apache-2.0 | `2c81af3bbe27` |
| 39 | [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) | MIT | `f3cd06a620e3` |
| 40 | [upstash/context7](https://github.com/upstash/context7) | MIT | `b5e81de84509` |
| 41 | [microsoft/autogen](https://github.com/microsoft/autogen) | CC-BY-4.0 | `004749e6b710` |
| 42 | [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | MIT | `0656245f0787` |
| 43 | [blader/humanizer](https://github.com/blader/humanizer) | MIT | `8c307f367c91` |
| 44 | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | MIT | `e85f3cbc2e4a` |
| 45 | [aaif-goose/goose](https://github.com/aaif-goose/goose) | Apache-2.0 | `e970eea8ac23` |
| 46 | [bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book) | Apache-2.0 | `dbc046eb896a` |
| 47 | [FlowiseAI/Flowise](https://github.com/FlowiseAI/Flowise) | NOASSERTION | `9291856d1ea4` |
| 48 | [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | MIT | `593377bb0487` |
| 49 | [multica-ai/multica](https://github.com/multica-ai/multica) | NOASSERTION | `dbdbb2991643` |
| 50 | [CherryHQ/cherry-studio](https://github.com/CherryHQ/cherry-studio) | AGPL-3.0 | `d81cdc44c9fe` |
| 51 | [run-llama/llama_index](https://github.com/run-llama/llama_index) | MIT | `619d74664e84` |
| 52 | [elder-plinius/CL4R1T4S](https://github.com/elder-plinius/CL4R1T4S) | AGPL-3.0 | `a4d3da04e633` |
| 53 | [DavidHDev/react-bits](https://github.com/DavidHDev/react-bits) | NOASSERTION | `e12c22192ac7` |
| 54 | [mudler/LocalAI](https://github.com/mudler/LocalAI) | MIT | `3934ee8e348b` |
| 55 | [microsoft/qlib](https://github.com/microsoft/qlib) | MIT | `543552324638` |
| 56 | [HKUDS/nanobot](https://github.com/HKUDS/nanobot) | MIT | `3d0f8feb77cf` |
| 57 | [zhayujie/CowAgent](https://github.com/zhayujie/CowAgent) | MIT | `3129c2b56b4a` |
| 58 | [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | MIT | `10ab613de30d` |
| 59 | [siyuan-note/siyuan](https://github.com/siyuan-note/siyuan) | AGPL-3.0 | `bfe36100477b` |
| 60 | [LibreChat-AI/LibreChat](https://github.com/LibreChat-AI/LibreChat) | MIT | `94ae8a419839` |
| 61 | [herdrdev/herdr](https://github.com/herdrdev/herdr) | Apache-2.0 | `6b526626f66e` |
| 62 | [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) | Apache-2.0 | `50c34e78c98d` |
| 63 | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | MIT | `eb066bd31a2b` |
| 64 | [AstrBotDevs/AstrBot](https://github.com/AstrBotDevs/AstrBot) | AGPL-3.0 | `0cd42bd4dd21` |
| 65 | [agno-agi/agno](https://github.com/agno-agi/agno) | Apache-2.0 | `6d5af04a72f7` |
| 66 | [ToolJet/ToolJet](https://github.com/ToolJet/ToolJet) | AGPL-3.0 | `7b1231d39bd0` |
| 67 | [pingcap/tidb](https://github.com/pingcap/tidb) | Apache-2.0 | `ab30f363d490` |
| 68 | [volcengine/OpenViking](https://github.com/volcengine/OpenViking) | AGPL-3.0 | `2260f6899e88` |
| 69 | [PostHog/posthog](https://github.com/PostHog/posthog) | NOASSERTION | `1c7d44833937` |
| 70 | [github/awesome-copilot](https://github.com/github/awesome-copilot) | MIT | `d85f762d6e52` |
| 71 | [mindsdb/mindshub](https://github.com/mindsdb/mindshub) | MIT | `d998b789ab08` |
| 72 | [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) | MIT | `c97d856a8fad` |
| 73 | [bytedance/UI-TARS-desktop](https://github.com/bytedance/UI-TARS-desktop) | Apache-2.0 | `3ac2cb8d946d` |
| 74 | [ashishpatel26/500-AI-Agents-Projects](https://github.com/ashishpatel26/500-AI-Agents-Projects) | MIT | `9beeb721c2af` |
| 75 | [patchy631/ai-engineering-hub](https://github.com/patchy631/ai-engineering-hub) | MIT | `be534adc47ae` |
| 76 | [CopilotKit/CopilotKit](https://github.com/CopilotKit/CopilotKit) | MIT | `4930320fa3fe` |
| 77 | [Dokploy/dokploy](https://github.com/Dokploy/dokploy) | NOASSERTION | `bce96fd75bf6` |
| 78 | [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router) | MIT | `057abaa1f955` |
| 79 | [khoj-ai/khoj](https://github.com/khoj-ai/khoj) | AGPL-3.0 | `ae229ca894c0` |
| 80 | [JCodesMore/ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template) | MIT | `ee3f5a2f31fd` |
| 81 | [continuedev/continue](https://github.com/continuedev/continue) | Apache-2.0 | `5522c6f44ca0` |
| 82 | [reworkd/AgentGPT](https://github.com/reworkd/AgentGPT) | GPL-3.0 | `18b073ab05b2` |
| 83 | [Tencent/WeKnora](https://github.com/Tencent/WeKnora) | NOASSERTION | `30658b7d43bf` |
| 84 | [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills) | Apache-2.0 | `54a798831d22` |
| 85 | [iOfficeAI/AionUi](https://github.com/iOfficeAI/AionUi) | Apache-2.0 | `11cd2a9a20d1` |
| 86 | [ifixai-ai/iFixAi](https://github.com/ifixai-ai/iFixAi) | Apache-2.0 | `92bb5d0a950e` |
| 87 | [topoteretes/cognee](https://github.com/topoteretes/cognee) | Apache-2.0 | `37f788bd2877` |
| 88 | [SigNoz/signoz](https://github.com/SigNoz/signoz) | NOASSERTION | `30839d390f46` |
| 89 | [conductor-oss/conductor](https://github.com/conductor-oss/conductor) | Apache-2.0 | `1488804170d1` |
| 90 | [iOfficeAI/OfficeCLI](https://github.com/iOfficeAI/OfficeCLI) | Apache-2.0 | `5e3e26278753` |
| 91 | [getzep/graphiti](https://github.com/getzep/graphiti) | Apache-2.0 | `afea04fecd34` |
| 92 | [vxcontrol/pentagi](https://github.com/vxcontrol/pentagi) | MIT | `cffed9485aa1` |
| 93 | [mksglu/context-mode](https://github.com/mksglu/context-mode) | NOASSERTION | `fc0fda3d2bf6` |
| 94 | [googleworkspace/cli](https://github.com/googleworkspace/cli) | Apache-2.0 | `a3768d0e82ad` |
| 95 | [ComposioHQ/composio](https://github.com/ComposioHQ/composio) | MIT | `fecf1bffae70` |
| 96 | [oraios/serena](https://github.com/oraios/serena) | NOASSERTION | `abb0a0f01b94` |
| 97 | [e2b-dev/awesome-ai-agents](https://github.com/e2b-dev/awesome-ai-agents) | NOASSERTION | `9596ab1e69fb` |
| 98 | [jackwener/OpenCLI](https://github.com/jackwener/OpenCLI) | Apache-2.0 | `aeaff2b796ef` |
| 99 | [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) | MIT | `a551c88389e3` |
| 100 | [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | Apache-2.0 | `3582a6841fe7` |
