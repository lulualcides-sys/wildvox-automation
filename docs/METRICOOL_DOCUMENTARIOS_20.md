# WildVox — vinte documentários por mês com Metricool Gratuito

**Decisão editorial desde 14/11/2026:** cancelar dependência de Publer e Zapier e publicar
**exclusivamente TikTok @wildvox** pelo Metricool (brand 7242311). Plano R$ 0.
Não contratar plugins pagos. Não criar publicações cruzadas no YouTube.

## Duração e narrativa
- Novas revisões de pauta a partir de **2026-11-15**: duração mínima de **60 s**;
  duração-alvo **90–180 s**; até **240 s (4 minutos)** no editor atual quando o
  material genuíno sustentar. Se houver assunto científico para mais de 4 minutos,
  estender o editor por capítulos originais antes de exigir render; **não** alongar
  uma cena repetida, vídeo congelado, narração artificial lenta ou B-roll irrelevante.
- Metricool aceita TikTok auto-publish entre 3 segundos e 10 minutos, MP4/MOV até 500 MB.
  Isso é o limite do provedor, não uma prova que o editor atual renderiza 10 minutos.
- Estrutura: pergunta factual → contexto → descoberta científica → explicação do mecanismo
  → contraprova/limite da hipótese → comparação real → consequência e fechamento.
  Usar capítulos e uma narração natural em pt-BR pelo Kokoro `pm_alex`.
- Como há vídeos mais longos, permitir cortes de **8–20 s** somente quando
  o animal real continua visível e a explicação justifica. Um único original nunca
  pode ser repetido como outra fonte. O limite vigente de 12 fontes autenticamente
  distintas pode tornar documentários próximos de 4 min inviáveis: **falhar sem
  substituição**. Aumentar a biblioteca ou desenvolver a montagem por capítulos.
- Não reproduzir roteiros de <15/11 para preencher a cota. Os shorts v1/v2 de 14/11
  permanecem protegidos, e recibos de REJECT continuam válidos para seus arquivos exatos.

## Calendário: limite de 20 por mês-calendário
- O relógio editorial e as datas devem seguir `America/Sao_Paulo`.
- `scripts/metricool_monthly_calendar.py` calcula **exatamente 20 datas distintas
  por mês**, espalhadas uniformemente do início ao fim. Em cada data planejar
  **no máximo um** novo documentário; manter a alternância **3 vídeos de gatos
  e 2 de outros animais** a cada grupo de cinco, se houver fatos e vídeos válidos.
- A cota oficial do Metricool gratuito conta **publicações efetivamente realizadas**,
  não simples agendamentos; reinicia no dia **1º**. O número real do planejador
  é a autoridade. Antes de programar, ler o histórico do Metricool, TikTok e os
  agendamentos no mês. Nunca programar outro vídeo se houver vinte publicados.
- Reservar as vagas já ocupadas pelos agendamentos. Nunca postar o mesmo MP4 ou
  tema duas vezes. Reconciliar `PUBLISHED`, `SCHEDULED` e `ERROR` sem reenvio automático.
- Se a cota de novembro estiver esgotada, editar/aprovar novos documentários
  para **dezembro de 2026**, sem tentar publicar em novembro nem reativar rascunhos
  vetados de 10/11. Consultas atuais retornaram zero linhas de analíticas TikTok:
  **isso não confirma cota disponível**. Verificar contador real no Metricool.
- Nenhuma execução verde de GitHub Actions altera sozinha o contador mensal.

## Publicação autorizada pelo usuário no Metricool
1. GitHub Actions renderiza no dia planejado com o contrato de 60–240 s
   e arquiva o ZIP original para inspeção independente, sem aceitar simples CI verde.
2. Revisor obtém o ZIP original, assiste ao vídeo completo e confere MP4/voz/legendas
   sincronizadas/frames, fonte científica, créditos, licença, arquivo SHA256,
   git blob e a revisão exata do JSON. **Só** um recibo independente por vídeo
   com `decision=APPROVE`, `visual_quality_approved=true` e hashes compatíveis
   autoriza agendamento. `publication_hold=true` permanece em rascunhos.
3. Após APPROVE, usar o app Metricool conectado, na brand 7242311, com
   `providers:[{network:'tiktok'}]`, `autoPublish:true`, `draft:false`,
   `media:[URL MP4 pública verdadeira]`, texto completo, créditos, etiqueta TikTok
   e horário do calendário. Não chamar uma API de outra conta nem usar
   Provider `youtube`, `instagram` ou `facebook`.
4. Confirmar que o resultado devolve **ID do post agendado e URL do planner**;
   depois verificar a publicação real no TikTok. Erros de limite ou licença
   são bloqueio, não sucesso. Não inventar URL pública, conversão ou métricas.

O conector Metricool do ChatGPT pode agendar diretamente, se estiver
disponível/permitido na execução autorizada; isto **não significa** que GitHub
Actions tem acesso grátis à API do Metricool. A API direta de integração
do Metricool exige plano Advanced/Custom, mas o conector de aplicativo
disponível no ChatGPT é uma capacidade distinta e não deve ser confundido
com o acesso REST gratuito. No caso de não haver conector utilizável durante a
automação, relatar a limitação sem substituir por Publer/Zapier.

Fontes oficiais:
- https://help.metricool.com/pt/principais-diferencas-entre-os-planos-gratuito-e-pagos-bl0v9
- https://help.metricool.com/pt/agende-e-publique-no-tiktok-bkepi
