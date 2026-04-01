# Agent Prompt

Copy-paste this into a new Claude Code conversation to get up to speed quickly.

---

```
Continue working on the trading system from docs/PLAN.md.

Context docs (read as needed, not all upfront):
- CLAUDE.md — project overview, commands, key constraints
- docs/ARCHITECTURE.md — system architecture, project structure, API endpoints, DB models, auth, design system
- docs/STRATEGY.md — signal pipeline, sentiment, commodity correlation, risk management
- docs/PLAN.md — completed history + current tasks + roadmap

Workflow:
1. Read docs/PLAN.md to find the next unchecked item under "Current / Next"
2. Break it into sub-items if needed, add them to the plan
3. Work through each sub-item — check it off as soon as it's done
4. When all sub-items are done, check off the parent and collapse into a summary line
5. Move to the next item

Verification:
- Web changes: `cd web && bun run build` must pass
- Python changes: `ruff check api/src/ bot/src/` should be clean
- Swift changes: `xcodebuild -project app/Trader.xcodeproj -scheme Trader -destination 'platform=iOS Simulator,name=iPhone 16' build 2>&1 | tail -5` must succeed

Deploy (commit and push first):
ssh -i your-ssh-key ubuntu@your-server \
  "cd ~/trader && git pull origin main && docker compose up -d --build"

Keep the plan consolidated — don't let completed sub-items bloat. When a step is fully done,
collapse its sub-items into a single summary line like the existing completed steps.
```
