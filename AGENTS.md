# WildVox — política de desenvolvimento (base Superpowers)

Método inspirado no projeto MIT [obra/superpowers](https://github.com/obra/superpowers); **não** afirma que a extensão está instalada em todos os agentes.

## Antes de modificar
1. Entender o problema e as etapas do render, o histórico da branch `media` e o estado dos posts.
2. Explicar o comportamento esperado com critérios que podem ser testados.
3. Escrever teste/regressão para o problema antes de tocar o gerador.
4. Corrigir apenas o necessário; manter áudio Michael, legendas seguras, 5 vídeos e QA atuais.
5. Rodar `python -m unittest discover -s qa -p 'test_*.py' -v`; não aprovar vídeo sem evidência visual.
6. Revisar risco de vazamento de token, conteúdo sem licença, fontes repetidas e publicação duplicada.
7. Checar o resultado do CI no GitHub antes de dizer que está funcionando.

**Produção:** não modificar `configs/daily.json` nem `scripts/generate_video.py` durante experimentos de editor; essas alterações podem acionar produção. FilmCraft fica só em experimento separado. Não publicar no TikTok sem material já renderizado e aprovado.

## Diagnóstico
Registrar causa raiz e reproduzir erro; não corrigir por tentativa aleatória. Depois conferir falhas adicionais e rollback.

## Fontes
- https://github.com/obra/superpowers
- https://github.com/storytold/filmcraft
