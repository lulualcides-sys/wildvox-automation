# WildVox — minidocumentários de curiosidades animais (padrão restabelecido em 2026-11-10)

## Objetivo
**Objetivo editorial:** ensinar uma curiosidade comprovada sobre o animal — comportamento, comida, brincadeira, sentidos, adaptações, habilidades ou comparação — e explicar o porquê ou o como. A história é sobre o **conhecimento transmitido**, não uma locução descrevendo cada clipe. O vídeo é B-roll que ilustra os fatos, nunca o contrário. Português brasileiro (pt-BR), TikTok @wildvox apenas.

**PROIBIDO:** roteiros descritivos do tipo "agora o gato olha", "depois ele anda", "aqui vemos outro animal", "o vídeo mostra...", listas de cenas independentes sem aprendizagem factual, interpretações de comportamentos não verificadas, comparação inventada, regravação de temas já publicados. Um vídeo tecnicamente bonito com esse defeito recebe VETO editorial.

**Estrutura factual:** gancho em pergunta ou fato surpreendente → curiosidade comprovada → comportamento observável → explicação biológica (mecanismo/causa, com incertezas quando existirem) → comparação concreta ou consequência → fechamento memorável. Fatos de biologia exigem pesquisa em fonte confiável independente das URLs do banco de imagens. Anotações, setas, rótulos, ilustrações e cortes aparecem quando ajudam a ensinar o mecanismo. Não exigir que B-roll de comportamento externo mostre estruturas internas; não apresentar imagens ilustrativas como prova do que não foi filmado.

**Trava de produção:** revisões preparadas a partir de 11/11/2026 exigem `curiosity_fact_sheet` com `hook_question`, `verified_fact`, `biological_explanation`, `comparison_or_consequence`, `visual_evidence_strategy` e `fact_sources` (cada uma: `claim`, `url`, `publisher`, `reference_title`). O gate em `qa/validate_curiosity_facts.py` rejeita fichas incompletas antes de renderizar, mas não substitui verificação científica individual nem inspeção visual do MP4. Históricos anteriores não são liberados automaticamente por essa regra.

## Estrutura obrigatória do `visual_plan`
Manter exatamente 5-7 blocos e o texto falado integral: a concatenação de `visual_plan[].text` deve equivaler exatamente a `script` após normalização prevista no gerador. Cada bloco precisa de `scene`, `tags` semânticas específicas que correspondam a fontes reais, e `story_role`. Papéis permitidos: `hook`, `setup`, `action`, `explanation`, `twist`, `payoff`. Primeiro bloco = `hook`; último = `payoff`; pelo menos um bloco intermediário = `action` e pelo menos um = `explanation` ou `twist`. Vários blocos podem ter o mesmo papel. Não são metadados top-level; integram cada vídeo.

- **Hook:** primeira fala cria pergunta, surpresa verificável ou conflito concreto, preferencialmente demonstrável pela primeira imagem. Evitar clickbait não comprovado, "you won't believe" e exageros.
- **Setup:** situar espécie e circunstância sem transformar o roteiro numa aula taxonômica.
- **Action:** usar uma cena real de comportamento como ilustração de uma afirmação zoológica relevante; nunca apenas relatar o movimento do clipe.
- **Explanation/twist:** ensinar mecanismo biológico ou causa/comparação baseada em fonte científica; se houver hipótese ou debate, indicar a incerteza com precisão.
- **Payoff:** entregar uma conclusão educativa surpreendente e verificável sobre o fato, com cena relevante; não resumir o que os clipes exibiram.

## Edição e áudio
- A partir de 10/11/2026 usar voz Kokoro `pm_alex` com `lang_code='p'`, narração e legendas em português brasileiro; preservar ritmo aprovado, legendas curtas e área segura vertical 1080x1920.
- Cortar imagens nos limites **medidos** de cada bloco sintetizado; para vídeos comuns manter tomadas de 6-8s, no máximo 8s, evitando congelamentos acima do limite existente.
- A primeira imagem deve provar ou introduzir o gancho; cada mudança de ideia exige um plano correspondente da espécie/ação; o encerramento usa a melhor demonstração do payoff.
- Destacar palavras-chave com a legenda já existente, sem cobrir o animal. Efeitos já disponíveis no gerador: setas vetoriais, círculos, caixas, rótulos animados e sem zoom artificial nos blocos hook/payoff, via scripts/cinematic_fx.py. Setas/caixas/círculos aparecem somente quando suas coordenadas são informadas e revisadas para a tomada real; não existe detecção automática de animais ou objetos.
- Preferir cenas documentais reais, sem usar imagens artificiais como se fossem filmagens. Nunca atribuir comportamento de outra espécie à espécie narrada.
- Verificar URLs, autoria e condições de licença na origem antes de aceitar o lote; manter créditos e requisitos CC/ShareAlike quando aplicável.

## Exemplo de papéis em cinco blocos (não copiar literalmente)
```json
[
  {"story_role":"hook","text":"...","scene":"See the archerfish aim at an insect","tags":["archerfish_aim"]},
  {"story_role":"setup","text":"...","scene":"Establish fish and prey above water","tags":["archerfish_surface"]},
  {"story_role":"action","text":"...","scene":"Show water jet striking an insect","tags":["archerfish_shoot"]},
  {"story_role":"explanation","text":"...","scene":"Demonstrate refraction with evidence-based illustration only when supported","tags":["archerfish_shoot"]},
  {"story_role":"payoff","text":"...","scene":"Return to the confirmed feeding behavior","tags":["archerfish_feeding"]}
]
```

## Critérios de aceite
1. Cinco entradas top-level do dia editorial correto, nenhuma metadata top-level adicional.
2. Histórias individuais com gancho, ação, mecanismo ou reviravolta e desfecho verificáveis; espécies e perspectivas variadas, sem duplicatas recentes.
3. Texto total da narração idêntico aos blocos; cenas e fontes correlacionadas; duração e fontes conforme validação **atual** do GitHub (atualmente cinco vídeos de 30-45s).
4. Passar QA estrutural. Render, áudio, visualização de quadros e autorização das fontes são verificações separadas: não declarar pronto/publicado só porque o JSON passou.
5. Não alterar o gerador principal durante experimentos de novos overlays; construir e testar esse recurso isoladamente antes de integrá-lo.


## Efeitos cinematográficos disponíveis a partir de 27/10
O gerador renderiza efeitos no próprio vídeo final usando FFmpeg/libass, sincronizados à duração real dos blocos da voz brasileira Alex. Não são comandos externos e não exigem serviços pagos.

Adicione, quando a tomada correspondente tiver enquadramento revisado:
- "overlay_label": "WATER SHOT" (texto curto animado, exibido brevemente);
- "fx": [{"type":"arrow","from":[0.18,0.55],"to":[0.73,0.42],"duration":1.6}] (seta amarela com entrada dinâmica);
- "fx": [{"type":"ring","center":[0.73,0.42],"radius":0.06}] (círculo que destaca e pulsa);
- "fx": [{"type":"box","center":[0.53,0.46],"width":0.25,"height":0.12}] (retângulo de destaque);
- "fx": [{"type":"label","position":[0.22,0.5],"text":"THE TARGET"}] (etiqueta localizada).

Todos os pontos usam coordenadas normalizadas [x,y] sobre a tela 9:16, com x entre 0,04 e 0,96 e y entre 0,10 e 0,82. Duração da animação por efeito entre 0,35 e 3s, no máximo **dois efeitos por bloco**. Os efeitos são opcionais se não for possível verificar composição e alvo: não aponte para lugares aleatórios nem marque a anatomia de outro animal. O enquadramento pode variar em clipes originais: priorize setas apenas em planos claramente revisados.

Os blocos "hook" e "payoff" não recebem zoom nem panorâmica artificial. Um rótulo de abertura/revelação é adicionado por padrão. Legacy batches sem story_role ficam visualmente inalterados. Não altera narração, fotogramas de origem, licenças ou regras de publicação.

**QA antes de declarar sucesso:** testes unitários em qa/test_cinematic_fx.py, render sintético real libass e filtros sem zoom, CI verde, depois revisão humana do enquadramento do vídeo real; testes sintéticos não aprovam a qualidade editorial de um vídeo final.


## Idioma padrão a partir de 10/11/2026
- Toda entrada nova de `configs/daily.json` deve conter `"language": "pt-BR"` e `"voice": "pm_alex"`.
- `title`, `script`, `caption`, `visual_plan[].text`, `overlay_label`, textos na tela e descrição devem ser em português brasileiro natural (sem traduções literais difíceis de entender). As tags descritivas internas podem continuar em inglês quando correspondem às fontes documentais.
- O gerador usa Kokoro `KPipeline(lang_code='p')` e voz masculina brasileira `pm_alex`. Legendas preservam acentuação; tempos vêm dos blocos de áudio realmente sintetizados.
- As publicações históricas em inglês permanecem intactas, mas não devem ser reencaminhadas como se fossem novas.
- `publication_hold=true` até testes reais de voz e renderização, licença, frames e revisão editorial, antes de qualquer agendamento pelo Metricool.
