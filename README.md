<div align="center">

# 🎓 Weekly Certification Loop

### A living archive of free AI and cloud certifications, refreshed every week by an autonomous agent loop

</div>

---

## 🚀 Why this exists
Great learning programs appear and expire quietly. This repository is maintained by a **weekly agent loop** that searches the major providers, verifies every link, drafts a clear summary, checks it for tone and accuracy, and publishes it here, so you never miss a free chance to level up.

**Providers tracked:** Microsoft · Google · GitHub Copilot · Anthropic Claude · Hugging Face · AWS · NVIDIA · xAI Grok · DeepSeek · Ollama

## 📅 Archive (newest first)

| Week | Opportunities | Providers |
|---|---:|---|
| [2026-10-08](2026-10-08/README.md) | 7 | AWS, Anthropic, Google, Hugging Face, Microsoft / GitHub, NVIDIA |
| [2026-10-01](2026-10-01/README.md) | 6 | AWS, Anthropic, Google, Hugging Face, Microsoft / GitHub, NVIDIA |

📒 The full run-by-run log is in [progress.md](progress.md).

## 🔁 How the loop works

| Stage | What happens |
|---|---|
| ⏱ **Heartbeat** | Windows Task Scheduler fires every 7 days |
| 🔍 **Discover** | A Claude Code agent searches provider sites within a strict budget (≤ 10 searches, ≤ 12 fetches, capped spend) |
| ✅ **Verify** | `loop/certloop.py` rejects runs with missing fields, non-official links, fewer than 5 finds or an overspent budget |
| ⚖️ **Maker-Checker** | The maker drafts the README and the checker enforces structure, clarity, professional tone and a motivational close |
| 📒 **Spine** | Each week is appended to `progress.md`, and every opportunity is tagged *new* or *returning* |
| 🔗 **Connector** | Commit `Weekly Certification Opportunities – DATE` and push |

Contributions and tips for new free programs are welcome: open an issue.

> 🌱 **Small, steady learning compounds. Check back every week.**
