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
- Destacar palavras-chave com a legenda já existente, sem cobrir o animal. Efeitos já disponíveis no gerador: setas vetoriais, círculos, caixas, rótulos animados e aproximação progressiva de até 4,5% nos blocos hook/payoff, via scripts/cinematic_fx.py. Setas/caixas/círculos aparecem somente quando suas coordenadas são informadas e revisadas para a tomada real; não existe detecção automática de animais ou objetos.
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
O gerador renderiza efeitos no próprio vídeo final usando FFmpeg/libass, sincronizados à duração real dos blocos da voz Michael. Não são comandos externos e não exigem serviços pagos.

Adicione, quando a tomada correspondente tiver enquadramento revisado:
- "overlay_label": "WATER SHOT" (texto curto animado, exibido brevemente);
- "fx": [{"type":"arrow","from":[0.18,0.55],"to":[0.73,0.42],"duration":1.6}] (seta amarela com entrada dinâmica);
- "fx": [{"type":"ring","center":[0.73,0.42],"radius":0.06}] (círculo que destaca e pulsa);
- "fx": [{"type":"box","center":[0.53,0.46],"width":0.25,"height":0.12}] (retângulo de destaque);
- "fx": [{"type":"label","position":[0.22,0.5],"text":"THE TARGET"}] (etiqueta localizada).

Todos os pontos usam coordenadas normalizadas [x,y] sobre a tela 9:16, com x entre 0,04 e 0,96 e y entre 0,10 e 0,82. Duração da animação por efeito entre 0,35 e 3s, no máximo **dois efeitos por bloco**. Os efeitos são opcionais se não for possível verificar composição e alvo: não aponte para lugares aleatórios nem marque a anatomia de outro animal. O enquadramento pode variar em clipes originais: priorize setas apenas em planos claramente revisados.

Os blocos "hook" e "payoff" recebem automaticamente um zoom de câmera sutil de até 4,5%. Um rótulo de abertura/revelação é adicionado por padrão. Legacy batches sem story_role ficam visualmente inalterados. Não altera narração, fotogramas de origem, licenças ou regras de publicação.

**QA antes de declarar sucesso:** testes unitários em qa/test_cinematic_fx.py, render sintético real libass e zoompan, CI verde, depois revisão humana do enquadramento do vídeo real; testes sintéticos não aprovam a qualidade editorial de um vídeo final.
