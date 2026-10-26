# WildVox — narrativa visual (a partir de 2026-10-27)

## Objetivo
Cada vídeo deve ser uma minihistória factual, contada em inglês americano, em vez de uma lista solta de curiosidades. Aplicar aos próximos lotes **sem reprocessar o lote de 26/10**. TikTok apenas; nenhuma ação desta política agenda/publica posts.

## Estrutura obrigatória do `visual_plan`
Manter exatamente 5-7 blocos e o texto falado integral: a concatenação de `visual_plan[].text` deve equivaler exatamente a `script` após normalização prevista no gerador. Cada bloco precisa de `scene`, `tags` semânticas específicas que correspondam a fontes reais, e `story_role`. Papéis permitidos: `hook`, `setup`, `action`, `explanation`, `twist`, `payoff`. Primeiro bloco = `hook`; último = `payoff`; pelo menos um bloco intermediário = `action` e pelo menos um = `explanation` ou `twist`. Vários blocos podem ter o mesmo papel. Não são metadados top-level; integram cada vídeo.

- **Hook:** primeira fala cria pergunta, surpresa verificável ou conflito concreto, preferencialmente demonstrável pela primeira imagem. Evitar clickbait não comprovado, "you won't believe" e exageros.
- **Setup:** situar espécie e circunstância sem transformar o roteiro numa aula taxonômica.
- **Action:** mostrar comportamento real em andamento, com verbo e objeto visualmente demonstráveis.
- **Explanation/twist:** explicar mecanismo, causa e consequência; se for hipótese científica, dizer isso explicitamente.
- **Payoff:** resolver o gancho, fechar com a revelação ou consequência visual, não repetir a introdução.

## Edição e áudio
- Preservar `am_michael`, voz em inglês americano, ritmo aprovado, legendas curtas e área segura vertical 1080x1920.
- Cortar imagens nos limites **medidos** de cada bloco sintetizado; para vídeos comuns manter tomadas de 6-8s, no máximo 8s, evitando congelamentos acima do limite existente.
- A primeira imagem deve provar ou introduzir o gancho; cada mudança de ideia exige um plano correspondente da espécie/ação; o encerramento usa a melhor demonstração do payoff.
- Destacar palavras-chave com a legenda já existente, sem cobrir o animal. Efeitos opcionais futuros: zoom moderado, seta, trajetória, etiqueta anatômica, comparação simples — **somente quando implementados e testados visualmente**. Este arquivo não implica que o renderizador já desenhe setas ou zooms.
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
