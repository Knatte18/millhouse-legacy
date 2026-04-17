# Gemini Paid Tier Setup Guide

How to configure Gemini CLI with a paid-tier API key so mill's reviewer pipeline gets stable, predictable latency. Written after empirical stress-testing on 2026-04-17 that showed free-tier OAuth produces 8× latency variance under concurrent load, while paid-tier API key delivers ~30 s worker response times with zero capacity-throttling.

---

## Why paid tier

**Free-tier OAuth (default `gemini` CLI authentication):**
- 60 RPM / 1000 RPD documented limits
- Subject to *capacity-based throttling* (Google's own banner: *"higher capacity-related errors during periods of high traffic"*)
- Empirical variance: 24 s best case, 381 s worst case on identical prompt (8×)
- Routes through `cloudcode-pa.googleapis.com` — the shared Code Assist pool

**Paid-tier API key (Tier 1, billing enabled):**
- ~100× the free-tier RPM
- No capacity-based throttling
- Empirical: 7-30 s per worker call, consistently
- Routes through `generativelanguage.googleapis.com` — standard pay-per-token Gemini API

For mill's ensemble reviewer (3 parallel bulk workers per review), free-tier concurrent-request-collision makes reviews unpredictable. Paid tier eliminates this.

Cost on paid tier (`gemini-2.5-flash`, $0.15 / $0.60 per M tokens):

- One ensemble review (3 workers × 12K input + 1.5K output): ~$0.008
- 100 reviews/month: ~$1
- 1000 reviews/month: ~$8

Set a budget cap (step 2 below) to hard-limit worst-case runaway.

---

## Prerequisites

- Google account (the one you use for Gemini CLI sign-in)
- Credit card (no charge unless you use; required to link billing)
- Windows/Linux/macOS with Node.js + npm for Gemini CLI

---

## Setup steps

### 1. Link billing to the Gemini project

1. Open [Google AI Studio → API keys](https://aistudio.google.com/app/apikey).
2. If you already have a key (typically "Default Gemini API Key" in "Default Gemini Project"), note its project ID. If not, click **Create API key** and pick a project (existing or new).
3. On the key's row, the *Billing Tier* column shows **"Free tier"** with a **"Set up billing"** link. Click it.
4. Cloud Console opens at the billing-linking page. Pick an existing billing account or create a new one. Confirm.
5. Wait for the confirmation banner: *"Gemini API Paid Tier activated"*. The key is now Tier 1.

### 2. Set a budget cap (protective — do this before anything else)

The cap is Google-side and hard-stops API calls if a runaway loop or bug blows past your comfort level.

1. [Cloud Console → Billing → Budgets & alerts](https://console.cloud.google.com/billing/budgets).
2. Click **Create budget**.
3. Scope: the billing account just linked.
4. Amount: `$5` (or whatever you're comfortable with). $5 funds ~600 ensemble reviews on `g25flash`.
5. Under **Actions**, enable *"Disable billing when budget reached at 100%"*. This is the hard cap.
6. Save.

Worst-case: mill bugs out with an infinite loop → API calls fail with 429 after $5 → mill stops making calls → you pay ≤ $5.

### 3. Set `GEMINI_API_KEY` at User scope (PowerShell)

Copy the key from AI Studio (click the `...oJDA` column to reveal full key, then copy).

```powershell
[Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'your-key-here', 'User')
```

Close and reopen any terminals / VS Code / Claude Code you want the key visible in. User-scope env vars are only inherited by processes started after the var was set.

Verify:

```powershell
[Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'User')
```

### 4. Install a Gemini CLI version that honors API-key auth

`gemini-cli 0.34.0` has a known bug: when OAuth cache is absent, the API-key path hangs indefinitely on the first call. Upgrade to `0.38.1` or later:

```powershell
npm install -g @google/gemini-cli@latest
gemini --version
```

### 5. Tell the CLI to use API-key auth (critical step)

The CLI stores an explicit auth preference in `%USERPROFILE%\.gemini\settings.json`. If it was set to `oauth-personal` (default after first interactive login), it overrides `GEMINI_API_KEY`. You must change it manually.

Open `%USERPROFILE%\.gemini\settings.json` in a text editor. You'll see something like:

```json
{
  "security": {
    "auth": {
      "selectedType": "oauth-personal"
    }
  }
}
```

Change `"oauth-personal"` to `"gemini-api-key"`:

```json
{
  "security": {
    "auth": {
      "selectedType": "gemini-api-key"
    }
  }
}
```

Save. No restart needed.

### 6. Verify

```powershell
echo "Say HELLO and nothing else" | gemini -p - --model gemini-2.5-flash
```

You should see `HELLO` come back in 2-5 seconds. If you get `Loaded cached credentials` followed by a 30-60 s wait, the CLI is still on OAuth — re-check step 5.

You can also check the endpoint the CLI is hitting by running with `--debug`; paid API-key routes to `generativelanguage.googleapis.com`, OAuth routes to `cloudcode-pa.googleapis.com`.

---

## Rollback to free-tier OAuth

If you want to switch back (e.g., to avoid billing during vacation):

1. Edit `%USERPROFILE%\.gemini\settings.json` and change `"selectedType"` back to `"oauth-personal"`.
2. Optionally unset the env var: `[Environment]::SetEnvironmentVariable('GEMINI_API_KEY', $null, 'User')`.
3. The OAuth creds in `%USERPROFILE%\.gemini\oauth_creds.json` are untouched — no re-login needed.

To switch between modes frequently without editing `settings.json`: run `gemini /auth` interactively and pick an auth type from the menu.

---

## Troubleshooting

**Symptom: "Loaded cached credentials" appears in stderr + slow calls**
→ CLI is on OAuth. Check `settings.json` step 5.

**Symptom: `cloudcode-pa.googleapis.com` in error messages**
→ Same — OAuth path active. Fix `settings.json`.

**Symptom: "No capacity available for model gemini-2.5-flash"**
→ OAuth capacity throttling. Either wait (can take minutes) or confirm `settings.json` is on `gemini-api-key`.

**Symptom: CLI hangs indefinitely with no output when `GEMINI_API_KEY` is set**
→ Known bug on CLI 0.34.0 when OAuth cache is absent. Upgrade to 0.38.1+.

**Symptom: "API keys are not supported by this API" or 403 PERMISSION_DENIED**
→ Billing not fully propagated OR you're on a model not included in your paid tier. Wait 5-10 minutes after linking billing; retry. Confirm model (`gemini-2.5-flash`) is available in your region.

**Symptom: Sudden spike in monthly bill**
→ Check [Cloud Console → Billing → Reports](https://console.cloud.google.com/billing/reports). You should have a budget cap (step 2); if you blew past it, the cap's 100% action didn't fire — revisit budget setup.

---

## How mill uses the paid-tier setup

Once the above is configured, no further mill-side changes are needed:

- `subprocess_util.run(...)` in `plugins/mill/scripts/millpy/core/subprocess_util.py` inherits `os.environ` which includes `GEMINI_API_KEY`.
- The child `gemini.CMD` process reads the env var and, since `settings.json` prefers `gemini-api-key`, uses the paid-tier endpoint.
- Ensemble reviewers (`g25flash-x3-sonnetmax`, etc.) get Tier 1 latency for Gemini worker dispatches.

When the `google-genai` SDK migration lands (see backlog), the CLI can be removed entirely — the SDK uses `GEMINI_API_KEY` directly with no `settings.json` dance.

---

## Related

- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) — official tier documentation
- [Gemini CLI authentication](https://geminicli.com/docs/get-started/authentication/) — upstream CLI auth docs
- [`plugins/mill/doc/local-llm/ollama-guide.md`](../local-llm/ollama-guide.md) — equivalent setup for local Ollama alternative
