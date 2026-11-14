# WildVox: GitHub → Zapier → Publer → TikTok @wildvox

Status: **not connected**. This is a safe release bridge, not an assertion that any TikTok post has been published. Until the owner finishes OAuth and a real end-to-end test, leave \`WILDVOX_PUBLER_ENABLED\` unset.

## Why this route?

Publer Free supports 3 social accounts and 10 queued posts per social account, replenished as posts publish. Its REST API, however, requires eligible Business/Enterprise accounts. Instead of inventing an API key on Free or paying for "Webhooks by Zapier", we can use a **two-step Zap**:

1. Trigger: **GitHub → New Issue**, repo \`lulualcides-sys/wildvox-automation\`, filter label **\`wildvox-publer-ready\`**.
2. Action: **Publer → Add Post to Queue / Auto Schedule**, account TikTok **exactly \`@wildvox\`**. Map:
   - **Media / video URL** ← GitHub Issue **Title** (the canonical public MP4 URL, and nothing else).
   - **Text / caption** ← GitHub Issue **Body** (complete, verified creator and license credits).
   - Provider: **TikTok only**. Publish: **Post Automatically**, not "Get a reminder".
   - Queue: use Publer's existing account-specific schedule. If your Zap action has only "Create Post" and requires a specific date instead of a queued option, **do not activate the bridge**; mapping cannot be verified without a different trigger/action arrangement.

Configure the Publer TikTok account's **Posting Schedule** for America/Sao_Paulo: **10:05, 12:40, 16:10, 19:35, 22:05**, seven days a week, video posts. Keep all slots unlabeled, unless you configure the same label in both Zap and Publer. Check account @wildvox (not @wildvox6) and confirm the privacy selection is available in Publer for that creator.

**Important cost:** Zapier Free has **100 tasks/month**, which is below the **150 tasks/month** needed for 5 posts every day of a 30-day month; after ~100 posts, the bridge will run out of Zapier tasks. Upgrade the automation tier or choose Publer Business API for sustainable 5/day. Publer itself can also enforce daily anti-spam limits. **Do not promise indefinite free 5/day.**

Sources:
- https://publer.com/help/en/article/what-is-included-in-publer-free-dliovh
- https://publer.com/help/en/article/how-to-connect-to-zapier-and-automate-your-workflows-18mun8n/
- https://publer.com/help/en/article/how-to-directly-post-tiktok-videos-1vpkmcs/
- https://help.zapier.com/hc/en-us/articles/32337438839565-What-s-included-in-Zapier-s-Free-plan
- https://zapier.com/apps/github/integrations

## GitHub setup and controls

After connecting Publer + TikTok and **testing the Zap mapping with a non-public test post**, set this repository's **Settings → Secrets and variables → Actions → Variables → \`WILDVOX_PUBLER_ENABLED=true\`**. This repository variable is intentionally absent by default.

The already existing workflow \`.github/workflows/wildvox-publer-zapier.yml\` will then check the current batch periodically. On a real, exact-match editorial receipt, it creates **one GitHub Issue** containing only the canonical video URL (title) and full caption (body). The issue label is created by the workflow if needed.

Never connect the Zap to all GitHub issues; filter by **\`wildvox-publer-ready\`**, otherwise unrelated issues could become TikTok posts.

The Python gate \`scripts/publer_handoff.py\` checks:
- Today's revision and 30–45s content, at most 5 distinct candidates
- pt-BR Kokoro pm_alex, >=8 video sources and scientific fact sheet
- Original \`media\` branch MP4, metadata, review and full attributed caption
- SHA256 MP4, \`git hash-object\` and canonical editorial config fingerprint
- Exactly one current-day approval receipt with GitHub run ID, original ZIP ID, factual/editorial checks **and explicit \`editorial_checks.visual_quality_approved=true\`**
- Never removes \`publication_hold=true\` from original editorial config
- Prevents a duplicate GitHub Issue for an identical media URL; no older MP4/day is reused
- Refuses release if today's five authorized slots have already passed

Existing rejected and published Metricool posts are **read-only historical evidence**. Never resend an old, pending, failed, or published video from Metricool through Publer. No Buffer, no YouTube.

## Verify separately

A GitHub handoff issue is **not a Publer post ID**, and a Publer scheduled item is **not TikTok PUBLISHED**. The owner's Publer connection and the first auto-publish receipt must be inspected separately. Record the exact public TikTok URL and a platform status; don't infer it from a successful Zap.

## Unblock production

The distribution switch does not fix missing new content. Daily Prep must create genuinely new verified zoological mini-documentaries; Github must render them; independent audiovisual QA must inspect the original Actions ZIP and publish an exact SHA-bound approval receipt. If any step fails, do not create a GitHub issue or schedule a post.
