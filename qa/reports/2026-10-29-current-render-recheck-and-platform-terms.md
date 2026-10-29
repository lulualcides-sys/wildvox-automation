# WildVox 2026-10-29 — independent current-render recheck and platform-terms analysis

**Scope and safety:** QA-only; no change to `configs/daily.json`, no render or publication. TikTok @wildvox ONLY; NEVER YouTube. This memo is an operational rights-risk review, **not a legal opinion or permission to publish**.

## Immutable render identity

- Latest Daily 5: [run 40897401387](https://github.com/lulualcides-sys/wildvox-automation/actions/runs/40897401387), completed SUCCESS, render head `0d1d8c45d20eeb4fbc5a572b60b9f797661ddc84`.
- Verified before this QA-only write: main `c47fc452653d06b298449c772bee7600ab8a1803`; `configs/daily.json` Git blob `c62ff7aceefc168a42445093e133edb9cde00b0f`. Five 2026-10-29 entries, all `publication_hold=true`.
- Independently downloaded all **five** latest-run ZIP artifacts, opened all **five** `*_review.jpg`, inspected **40** source-preview strips (eight per candidate), and extracted **30** fresh midpoint frames directly from the five MP4 files. No previous-run visual verdict was reused.
- Independently rescanned each entire MP4 with `ffmpeg -vf fps=8,scale=320:-2,freezedetect=n=-40dB:d=1.0,blackdetect=d=0.5:pix_th=0.07 -an -f null -`; all five exited 0, with **zero** >=1s near-static intervals and **zero** >=0.5s black intervals. All five are 1080x1920 with audio; durations 30.425–36.600s.
- MP4 SHA-256, in order snow / hummingbird / caribou / honeybee / fox: `5ad1daf6a8768fc4c580c61f6fe1ecf5ac8de331f3d94fc231390c9c49d9fc6e`, `b5016100d3fdfcb6fafabdfd3849c919fa0b4e5c6a0a9d3b05adf537ff1f42fb`, `b2121373c66f80bf962e17d7315d5ac408a684a5ecbedeedad1f8900e4e8dfcb`, `46aa48ddc7cf7d4e577518ddfaede68407d286a60af48aeb93c85b8d1e453392`, `148785e80c87c7b2283f080b54843990649a8453f0594015457430aeb5d35786`. These match the previous independent audit **because the render itself has not changed**, not because prior QA was substituted.
- Six real Kokoro narration timeline blocks per MP4 metadata. Actual captions appear in the lower center and hooks in the upper center; the ASS Caption style uses bottom margin 390px, left/right margins 150px. No platform screenshot was available to prove final TikTok UI overlay clearance.

## Editorial findings (not approved)

1. **Snow leopard:** opening bone gnawing and final cubs are visible; explanatory shot at ~18s uses very dark, low-resolution archival footage, and repeated creator/filming families remain. Source `Snow Leopard eating.ogv` historical cheetah label was challenged in 2008, but embedded `Sebastian Welp` versus Commons `Squirrel83` creator identity still needs rights reconciliation. See `2026-10-29-snow-leopard-source-provenance.md`.
2. **Hummingbird:** opening nestling wingbeats and separate adult footage are visible. Some birds are tiny, and source 07's dark bird is hard to identify among foliage. Species-neutral title correctly avoids asserting the opening nestling is Anna's; the footage does not document one individual's development.
3. **Caribou:** hook now shows a nearby animal and North America scene is improved; later grazing reindeer are distant, and the final enclosure is visibly captive. Narration distinguishes settings.
4. **Honeybee:** authentic macro foraging and hive traffic appear, but at least one flower shot shows a tiny soft-focus bee and a hive exterior shot is wide. No fake fanning claim should be added.
5. **Red fox:** genuine hunting/scavenging/playing scenes and active young foxes, but early subjects are distant; scavenging clip prominently contains discarded plastic litter. This matches the spoken scavenging example but is visually unattractive.

All five remain **editorial conditional / not approved**, despite clean technical QA. No source replacement or costly rerender is justified without first verifying a specific better original clip and its license.

## Official Creative Commons and TikTok terms — precise boundary

- Creative Commons' official [FAQ on sharing CC content to social platforms](https://creativecommons.org/faq/#do-i-need-to-worry-about-website-terms-of-service-when-i-share-cc-licensed-content-on-social-media-platforms) explicitly explains that a user **cannot sublicense** third-party CC rights to the platform, while posting properly licensed third-party material to a social service is **not automatically forbidden**; the user must satisfy attribution and all applicable license conditions. Avoid both categorical claims ("all CC BY-SA TikToks are banned" or "the license alone clears TikTok").
- TikTok's official [US Terms of Service, last updated 2026-07-15, section 3.5](https://in.tiktok.com/legal/page/us/terms-of-service/en) say that uploading Your Content grants TikTok a worldwide, assignable, **sublicensable** license, including derivatives, distribution, and technology/model development. A creator of a WildVox edit cannot grant sublicensing rights to third-party CC footage that the creator does not own. The precise extent of the uploader's grant for incorporated third-party footage, and the applicable terms for the **Brazil-connected account**, have **not** been independently resolved. US audience targeting does not by itself prove US Terms govern this account.
- The official [TikTok IP policy in Portuguese](https://in.tiktok.com/legal/page/global/copyright-policy/pt-BR) warns against unlicensed use and account penalties; it does not supply a blanket CC BY-SA compatibility clearance.
- The repo's `qa/credits/2026-10-29.md` provides author, source URL, license, edit notice and intended CC BY-SA 4.0 adapter notice. The five planned captions are 543–629 characters, include creator names and a manifest pointer, but **actual TikTok caption visibility, link accessibility, and applicable platform permissions cannot be verified without a real post**. Do not create a test publication that bypasses the hold.
- **Practical mitigation for future Daily Prep:** preferentially source authentic **CC0 / verified public-domain** footage (or obtain explicit creator permissions covering TikTok's sublicensing requirements), retaining provenance records. This reduces platform sublicensing uncertainty; it does not waive other rights or visual QA. For today's mixed CC BY-SA footage, keep holds pending applicable-account terms/rights clarification.

## Publication status at recheck

Metricool brand 7242311 scheduled posts for 2026-10-29: `[]`; TikTok TKPO01 analytics rows for 2026-10-29: `[]`. No real Metricool post IDs; no confirmed publication. Only future 16:10, 19:35 and 22:05 São Paulo slots remain after 14:30. Never backfill earlier slots, never exceed five/day, never use YouTube.

**Decision:** all `publication_hold=true`; no scheduling, no config push, no render. Technical checks pass; editorial and platform/license clearance do not. Preserve all five MP4s and source evidence for targeted improvements and tomorrow's fresh prep.
