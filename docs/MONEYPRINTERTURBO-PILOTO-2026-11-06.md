# WildVox — piloto isolado MoneyPrinterTurbo (06/11/2026)

Ferramenta oficial: https://github.com/harry0703/MoneyPrinterTurbo (MIT no repositório). **Não substitui** o FFmpeg/Kokoro Michael, as legendas nem o pipeline de publicação atualmente aprovado.

## O que foi integrado

`scripts/moneyprinterturbo_pilot.py` prepara a CLI oficial do MoneyPrinterTurbo com **8–12 vídeos locais distintos**, já revisados, um roteiro narrativo aprovado e o arquivo de voz WildVox Michael **pré-gerado**. O piloto **nunca chama a geração final**, porque o CLI upstream informa que a etapa `video` pode iniciar integrações de cross-posting. Em vez disso, executa até a etapa segura `--stop-at materials` com `--video-source local` e `--custom-audio-file`; TTS externo, legenda e música ficam desligados nesse teste. A etapa não comprova qualidade de edição.

**Apenas materiais de teste aprovados:** não aceitar vídeo externo não verificado nem materiais sem licença/atribuição documentada. As flags de aprovação são declarações do curador; **não** provam por si só a autoria ou os direitos.

## Piloto local, nunca em produção

Crie um plano JSON local não versionado com `script`, `narration_file` e `sources` (8–12 objetos com `file`, `source_page` Commons, `license` e `reviewed: true`). O arquivo de voz e todos os vídeos devem existir no diretório passado em `--assets-root`. Não armazenar tokens, arquivos privados, mídias ou cópias de vídeos no repositório público.

```bash
# somente verifica/mostra comando (nenhum serviço inicia):
python scripts/moneyprinterturbo_pilot.py \
  --plan /tmp/wildvox-approved-plan.json \
  --assets-root /tmp/wildvox-approved-assets \
  --mpt-root /tmp/MoneyPrinterTurbo

# execução explícita: só teste de materiais, sem vídeo e sem TikTok:
python scripts/moneyprinterturbo_pilot.py \
  --plan /tmp/wildvox-approved-plan.json \
  --assets-root /tmp/wildvox-approved-assets \
  --mpt-root /tmp/MoneyPrinterTurbo --execute
```

Requer clone externo do MoneyPrinterTurbo e instalação consciente de suas dependências no ambiente local. Este PR **não** instala esses pacotes, usa GPU, chama APIs pagas, gera/renderiza novos vídeos ou altera `configs/daily.json`/`scripts/generate_video.py`.

## Comparação / critério de promoção

- **Base (WildVox):** áudio Kokoro Michael, 5 vídeos, 3 sobre gatos e 2 sobre outros animais por lote, duração e cadência do sistema aprovado, proveniência de mídia e legendas sincronizadas.
- **Piloto (MPT):** validar somente preparação de materiais locais e isolamento contra publicação. Executar `python -m unittest discover -s qa -p 'test_*.py' -v` e registrar casos rejeitados.
- **Não medido:** duração e aparência de vídeos, sincronia de legendas, taxa de aprovação visual, tempo/custo de renderização ou alcance no TikTok. Só considerar um teste de **vídeo final offline** após revisar como impedir qualquer cross-posting do upstream, com autorização e ambiente sem credenciais.
- Se o piloto não superar objetivamente o pipeline atual, **descartar** a dependência em vez de adicioná-la à produção.

O script e os testes não são invocados por nenhum workflow agendado.
