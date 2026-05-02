# Third-Party Notices — Vendored Skills

The skill directories under `.claude/skills/` (other than `verdict-house-rules/`) are vendored verbatim from upstream MIT-licensed projects. Their copyright and license terms are preserved below per MIT's notice clause. License compatibility verified per CLAUDE.md §3.8 — see `docs/SKILLS_LICENSE_AUDIT.md` for the audit log.

Verdict will pull updates from upstream periodically; do not edit vendored files in place. Verdict-specific behavior lives in `verdict-house-rules/` and overrides upstream where they conflict (see `docs/SKILLS_FRAMEWORK.md`).

---

## Superpowers — Jesse Vincent (obra/superpowers)

**Source:** https://github.com/obra/superpowers
**Vendored at commit:** `e7a2d16476bf042e9add4699c9d018a90f86e4a6` (2026-04-27)
**License:** MIT
**Skills vendored (14):**

- `brainstorming/`
- `dispatching-parallel-agents/`
- `executing-plans/`
- `finishing-a-development-branch/`
- `receiving-code-review/`
- `requesting-code-review/`
- `subagent-driven-development/`
- `systematic-debugging/`
- `test-driven-development/`
- `using-git-worktrees/`
- `using-superpowers/`
- `verification-before-completion/`
- `writing-plans/`
- `writing-skills/`

```
MIT License

Copyright (c) Jesse Vincent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## mattpocock/skills — Matt Pocock

**Source:** https://github.com/mattpocock/skills
**Vendored at commit:** `b843cb5ea74b1fe5e58a0fc23cddef9e66076fb8` (2026-04-30)
**License:** MIT
**Skills vendored (2):**

- `grill-me/` (originally `skills/productivity/grill-me`)
- `grill-with-docs/` (originally `skills/engineering/grill-with-docs`)

```
MIT License

Copyright (c) Matt Pocock

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Rejected (license incompatible)

The following skill packs were evaluated and **rejected** per CLAUDE.md §3.8:

| Pack | License | Reason |
|---|---|---|
| `trailofbits/skills` | CC-BY-SA-4.0 | Share-alike incompatible with vendoring into a MIT repo. Read upstream as reference; do not vendor. |
