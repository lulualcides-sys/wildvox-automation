# WildVox → Buffer (TikTok somente)

## Status

Código do publicador e workflow instalados no GitHub. **A publicação automática fica DESATIVADA até configurar a conta, o secret e a variável de ativação.** A existência do workflow não significa que vídeos foram publicados.

## Ativação segura

1. Conectar o TikTok `@wildvox` na conta Buffer (Free) e definir o canal para publicação automática, não "Notify Me".
2. No Buffer, gerar uma **nova** chave pessoal em Settings → API. Nunca publicar ou compartilhar a chave em commits, screenshots, issues ou chats.
3. Abrir https://github.com/lulualcides-sys/wildvox-automation/settings/secrets/actions e cadastrar `BUFFER_API_KEY` como **Repository secret** (valor exato da chave nova).
4. Em Settings → Secrets and variables → Actions → Variables, cadastrar `WILDVOX_BUFFER_ENABLED` com valor `true`.
5. Em Actions, executar manualmente **WildVox Buffer TikTok (Daily 5)** com `dry_run=true` para validar um lote **do dia**, antes de executar `dry_run=false`. Não executar `dry_run=false` antes de conferir os vídeos.
6. Desativar o agendador antigo via Metricool (WildVox Final Publish) ao ativar o Buffer, para não agendar duas vezes os mesmos vídeos.

## Execução automática

- 04h45: automação externa prepara `configs/daily.json` com cinco animais NOVOS e `revision` iniciado por data local `YYYY-MM-DD`.
- 05h30: GitHub Actions `WildVox Daily 5` renderiza os cinco MP4 e publica MP4, meta e review na raiz do branch `media`.
- 06h45: revisão automática já existente no ChatGPT.
- 08h45 (11h45 UTC): novo GitHub Action busca apenas vídeos de configuração **atualizada no dia**, confirma que houve renderização bem-sucedida depois do commit e que os artefatos batem com os metadados, descobre o canal TikTok @wildvox e agenda via GraphQL `https://api.buffer.com`.

Horários pretendidos (São Paulo): **10h05, 12h40, 16h10, 19h35, 22h05**. Se algum horário já passou, os slots restantes são utilizados sem postar vídeos retroativamente.

## Proteções

- Não usa token no repositório ou nos logs. Usa exclusivamente `BUFFER_API_KEY` fornecido como segredo ao job.
- `WILDVOX_BUFFER_ENABLED` precisa ser `true` para habilitar o agendador de produção.
- Rejeita `configs/daily.json` com revisões antigas, jobs antigos e ativos incompletos.
- Exige apenas um canal Buffer TikTok cujo nome inclua `wildvox`; falha se desconectado ou pausado.
- Antes de criar posts, lê publicações `scheduled`, `sent` e `error`, e evita reenviar conteúdo repetido.
- Respeita a fila gratuita de até **10 agendamentos simultâneos por canal**, limita hashtags a 5 incluindo #WildVox e informa IDs retornados pelo Buffer.
- Arquivos MP4 precisam permanecer disponíveis via GitHub publicamente até serem publicados.
- Sucesso ao agendar não equivale a sucesso da publicação no TikTok. Conferir status `sent` depois, e investigar erros reais.
- Se houver falha, o job termina em erro e NÃO afirma que o vídeo foi publicado.

## Limitações importantes

O plano gratuito Buffer não tem teto fixo de 10 publicações no mês: a limitação é 10 **posts pendentes na fila ao mesmo tempo**. Se diariamente saírem 5, a fila libera capacidade. A API Free possui limites de requisições; a integração só faz consultas necessárias.

A conexão Buffer ainda precisa ser testada com a conta real. Se o script não encontrar o canal ou o Buffer recusar `createPost`, não forçar publicação, não tentar contornar restrições e não usar browser automatizado como substituto.
