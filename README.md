# WildVox Automation

**Verificações de desenvolvimento:** CI `WildVox — revisão Superpowers / QA` verifica sintaxe e executa os validadores reais do gerador para cinco vídeos, duração, fontes e duplicações sem instalar IA/FFmpeg ou disparar TikTok. Política de regressões: `AGENTS.md`. FilmCraft é experimento isolado, resultado documentado em `docs/FILMCRAFT_EVALUATION.md`; a edição FFmpeg/Kokoro continua ativa.

Automated TikTok-only @wildvox animal-curiosity mini-documentaries in Brazilian Portuguese. Narration uses Kokoro TTS (`pm_alex`), verified zoological facts and comparisons, licensed real B-roll, FFmpeg, and GitHub Actions. **Do not use shot-by-shot descriptive narration.** New daily revisions from 2026-11-11 require evidence-backed `curiosity_fact_sheet` (see `configs/editorial_policy.json` and `qa/validate_curiosity_facts.py`) before rendering; technical QA does not authorize publishing.
