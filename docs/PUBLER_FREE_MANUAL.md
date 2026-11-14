# WildVox — Publer gratuito (sem Zapier)

**Destino:** apenas TikTok @wildvox. **Custo mensal dos serviços:** R$ 0, sujeito às condições dos planos gratuitos.

## O que é realmente automático
O GitHub pode produzir os vídeos e verificar os critérios técnicos e editoriais.
O Publer pode publicar sozinho nos horários agendados. **A importação
inicial de cada novo vídeo para Publer precisa ser realizada pelo titular da
conta**: não há uma API direta gratuita do Publer configurada no WildVox.

## Configure uma vez no Publer
1. Publer → Social Accounts: confirme TikTok @wildvox, e não outra conta.
2. Publer → Posting Schedule: configure America/Sao_Paulo,
   todos os dias: 10:05, 12:40, 16:10, 19:35 e 22:05.
3. Publer Free permite até 10 posts agendados simultaneamente por conta,
   e até 15 vídeos TikTok por janela de 24h, sujeitos a mudanças/limites
   do provedor. Não presumir que um agendamento foi publicado.

## Pacote copiável no GitHub, sem baixar o MP4
1. No GitHub: Actions → **WildVox - pacote gratuito Publer** →
   Run workflow → Run workflow.
2. Abra a execução concluída e a aba **Summary**. O script gera uma
   URL pública direta do MP4 e a legenda integral com créditos **somente**
   para candidatos atuais com recibo independente, SHA256 e git blob
   compatíveis. Se não houver aprovação, o Summary diz para não publicar.
3. Abra https://app.publer.com/ → Create, selecione TikTok @wildvox.
4. Em Media, escolha a opção de importar **URL** e cole a URL terminada
   em .mp4 exibida no Summary. Aguarde o Publer processar o vídeo.
5. Cole a legenda integral e os créditos. Escolha **AutoSchedule**
   e confira os próximos slots **futuros**. Não escolha lembrete/manual.
6. Confira em Scheduled; mais tarde, consulte o status Published
   e a URL pública real no TikTok. Registre a URL para deduplicação.

Se uma URL não abrir diretamente um MP4 acessível, não agende; corrija a
branch media primeiro. Não publicar vídeos antigos ou cuja mídia tenha
mudado de hash, nem os drafts rejeitados no Metricool em 10/11.

## O Zapier foi descartado
Não ative o Zap anterior GitHub → Publer. A integração exige etapas
ou limites incompatíveis com o custo zero e a meta de cinco/dia.
O workflow legado **WildVox Publer approved handoff** deve permanecer
desativado, sem criar Issues para publicação. O novo workflow é
somente um relatório, sem acesso de escrita a redes sociais.

## Bloqueio atual
Em 14/11/2026 o daily.json ainda referencia somente o candidato de 12/11
com publication_hold=true. O pacote não aprovará nem reciclará
esse vídeo. São necessários clipes novos, fonte científica,
renderização real e QA independente antes de abrir a fila do Publer.

Fontes oficiais:
- https://publer.com/help/en/article/what-is-included-in-publer-free-dliovh/
- https://publer.com/help/en/article/how-to-upload-videos-to-publer-from-external-urls-sxubil/
- https://publer.com/help/en/article/how-to-automatically-schedule-posts-jj58si/
- https://publer.com/docs/getting-started/rate-limits
