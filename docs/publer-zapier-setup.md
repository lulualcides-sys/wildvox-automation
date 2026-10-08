# WildVox → Publer via Zapier

This bridge keeps Publer API credentials out of GitHub and works with Publer's Zapier integration.

## One-time setup

1. In Publer, connect the WildVox TikTok account.
2. In Publer, create the TikTok posting schedule with the five daily video slots:
   - 10:05
   - 12:40
   - 16:10
   - 19:35
   - 22:05
   Timezone: America/Sao_Paulo.
3. In Zapier, create a Zap with:
   - Trigger: Webhooks by Zapier → Catch Hook.
   - Action: Publer → Create Post or Auto Schedule Post.
4. Connect the Publer workspace and select the WildVox TikTok account.
5. Map incoming fields:
   - Text → `text`
   - Media → `media_url`
   - Account → WildVox TikTok
   - State → Scheduled / Auto Schedule
6. Configure TikTok privacy and engagement fields required by Publer/TikTok for each post.
7. Copy the Zapier Catch Hook URL.
8. Add the GitHub Actions repository secret:
   - Name: `PUBLER_ZAPIER_WEBHOOK`
   - Value: the Zapier Catch Hook URL.
9. Publish the Zap.

## Runtime

After a successful `WildVox Daily 5` workflow, `WildVox Publer Bridge` sends exactly five JSON payloads to Zapier. Each payload includes the canonical public MP4 URL, caption, title, metadata URL, review image URL, and order.

Metricool publishing is intentionally disabled while the Publer bridge is used.
