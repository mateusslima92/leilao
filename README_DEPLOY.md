# Rodar o Leilão PB na nuvem (GitHub Actions) — passo a passo

Tira a dependência do seu Mac estar ligado. Todo dia às **07:00 (Brasília)** o GitHub:
baixa o CSV da Caixa → analisa + aplica os alarmes → manda o WhatsApp → publica o painel
atualizado numa URL fixa. Custo: **R$ 0**.

> **Privacidade:** o repositório é **público** (necessário pro painel grátis), então os
> telefones dos destinatários **não** ficam no código nem no painel — eles vivem só num
> *Secret* do GitHub. O resto (imóveis, critérios dos alarmes, painel) é dado público da Caixa.

---

## 1. Criar o repositório e subir o projeto

No site do GitHub: **New repository** → nome `leilao` → **Public** → *Create*
(não marque "Add README"). Depois, no Terminal, dentro da pasta do projeto:

```bash
cd "/Users/mateuslima/Desktop/Claude Code Projects/leilao"
git init
git add .
git commit -m "primeiro commit"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/leilao.git
git push -u origin main
```

> O `.gitignore` já garante que `whatsapp_secrets.json` e `recipients.secret.json`
> **não** sobem. Confira depois do push que esses dois arquivos não aparecem no GitHub.

## 2. Cadastrar os Secrets

No repositório: **Settings → Secrets and variables → Actions → New repository secret**.
Crie **quatro**:

| Nome do Secret | Valor (copie de onde) |
|---|---|
| `ZAPI_INSTANCE_ID` | campo `instance_id` do seu `whatsapp_secrets.json` |
| `ZAPI_TOKEN` | campo `token` |
| `ZAPI_CLIENT_TOKEN` | campo `client_token` (Token de Segurança da Conta, aba Security do Z-API) |
| `LEILAO_RECIPIENTS` | conteúdo **inteiro** do arquivo `recipients.secret.json` |
| `SCRAPERAPI_KEY` | API key da sua conta gratuita em https://www.scraperapi.com (baixa o CSV via IP residencial; sem ela, a Caixa bloqueia o download na nuvem) |

> Se mesmo com a `SCRAPERAPI_KEY` a Caixa bloquear, crie a **Variable** (não Secret)
> `SCRAPERAPI_ULTRA` = `true` em *Settings → Secrets and variables → Actions → Variables*,
> que liga proxies mais fortes (gasta mais créditos).

O `LEILAO_RECIPIENTS` é um JSON neste formato (use o conteúdo real do seu
`recipients.secret.json`, que já foi gerado com seus destinatários atuais):

```json
{"a1780663816187": ["+55DDDNUMERO", "+55DDDNUMERO", "ID-DO-GRUPO-group"]}
```

## 3. Ativar o GitHub Pages

**Settings → Pages → Build and deployment → Source: GitHub Actions.** Só isso.

## 4. Testar agora (sem esperar as 07h)

**Actions** (aba do topo) → workflow **"Leilão PB — rotina diária"** → **Run workflow**.
Acompanhe os passos. Ao terminar:

- O painel fica em **`https://SEU_USUARIO.github.io/leilao/`** (aparece também em Settings → Pages).
- Se houver oportunidade nova que bata num alarme, o WhatsApp é enviado.

## 5. Pronto

Daí em diante roda sozinho todo dia, com o computador ligado ou não.

---

## Como mudar coisas depois

- **Destinatários do WhatsApp:** edite o Secret `LEILAO_RECIPIENTS` (não mexe no código).
  Formato: `{"<id_do_alarme>": ["+55DDDNUMERO", "id-do-grupo"]}`.
- **Critérios dos alarmes** (bairros, área, score, etc.): edite no painel local e suba o
  `leilao_state.json` atualizado (`git add leilao_state.json && git commit && git push`).
  Lembre de deixar `recipients` vazio nele — quem manda nos telefones é o Secret.
- **Horário:** mude o `cron` em `.github/workflows/diario.yml` (está em UTC; 07h BRT = `0 10 * * *`).

## Aviso por e-mail quando falhar

O workflow **falha de propósito** (depois de rodar tudo com o último CSV bom) quando a
Caixa não devolve um CSV novo no dia. Isso dispara o e-mail nativo do GitHub. Para receber:
em **github.com → Settings → Notifications → Actions**, marque **Email** e
*"Only notify for failed workflows"*. O e-mail vai para o endereço da sua conta.

## Importante

- **Desative o job local do Mac** pra não duplicar aviso:
  `launchctl unload ~/Library/LaunchAgents/com.mateus.leilao-diario.plist`.
  (O envio é idempotente em cada máquina, mas nuvem e Mac têm registros separados.)
- O **cron do GitHub pode atrasar** alguns minutos em horário de pico — normal.
- Se a Caixa bloquear o download naquele dia (anti-robô), a rotina **segue com o último
  CSV bom** já no repo — não quebra.
- O GitHub **pausa o agendamento após 60 dias** sem nenhuma atividade no repo. Um clique em
  "Run workflow" (ou qualquer commit) reativa.
