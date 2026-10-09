# WildVox x FilmCraft — avaliação segura

**Status:** teste de compatibilidade da distribuição 0.2.0 no GitHub Actions, não substituição da edição.
Fonte: https://github.com/storytold/filmcraft (MIT/Apache-2.0).
Roadmap publicado em 2026-10-05: ~50–60% pronto para edição real; portanto não colocar em produção sem validação.

O workflow `WildVox — teste FilmCraft sem publicar`:
1. Gera um vídeo sintético 9:16 com o FFmpeg padrão.
2. Baixa somente a release oficial FilmCraft v0.2.0 para Linux, verifica SHA-256 publicado.
3. Verifica se a versão distribuída inclui `filmcraft-cli` e tenta `commands`.
4. Publica apenas JSON/metadata com resultado; não mexe em vídeo real, TikTok, workflow diário ou voz.

**Próximos critérios de aceite:** render completo de 30–45 s (com clipes, am_michael, música controlada e legendas menores), comparação de duração, nitidez, áudio LUFS, sincronismo, tempo de render e consumo. CLI disponível **não** equivale a render pronto.

**Condição:** preservamos FFmpeg/Kokoro até FilmCraft superar o processo em vídeos reais com QA aprovada. O GitHub não possui GPUs garantidas no plano gratuito.
