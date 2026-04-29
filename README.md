# Pipedrive RPA — Exportação Diária

RPA em Python + Playwright que acessa o Pipedrive, aplica um filtro salvo e exporta o relatório para o Google Drive todos os dias.

---

## Estrutura

```
pipedrive-rpa/
├── rpa/
│   ├── pipedrive.py   # Automação do navegador (Playwright)
│   └── gdrive.py      # Upload para o Google Drive
├── main.py            # Agendador (APScheduler)
├── Dockerfile
├── requirements.txt
├── .env.example       # Template de variáveis — copie para .env
└── .gitignore
```

---

## Configuração local

```bash
cp .env.example .env
# Edite o .env com suas credenciais
pip install -r requirements.txt
playwright install chromium
python main.py
```

Para rodar imediatamente sem esperar o horário agendado:
```bash
RUN_ON_START=true python main.py
```

---

## Google Drive — Service Account

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Crie um projeto (ou use um existente)
3. Ative a **Google Drive API**
4. Crie uma **Service Account** → gere uma chave JSON
5. Compartilhe a pasta do Drive com o e-mail da service account (ex: `rpa@projeto.iam.gserviceaccount.com`) com permissão de **Editor**
6. Cole o JSON da chave na variável `GOOGLE_SERVICE_ACCOUNT_JSON` do `.env`

---

## Deploy no Easypanel

1. Suba o código no GitHub (`.env` e `credentials/` estão no `.gitignore` ✅)
2. No Easypanel, crie um novo serviço **App** → conecte ao repositório
3. Em **Environment Variables**, cadastre todas as variáveis do `.env.example`
4. O Easypanel fará o build do `Dockerfile` automaticamente
5. O container inicia e aguarda o horário agendado

> **Dica:** Para testar o deploy imediatamente, sete `RUN_ON_START=true` nas variáveis do Easypanel.

---

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `PIPEDRIVE_EMAIL` | E-mail de login |
| `PIPEDRIVE_PASSWORD` | Senha (injetada pelo Easypanel, nunca no código) |
| `PIPEDRIVE_DOMAIN` | Subdomínio da empresa no Pipedrive |
| `PIPEDRIVE_FILTER` | Nome exato do filtro salvo |
| `GDRIVE_FOLDER_ID` | ID da pasta de destino no Drive |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | JSON da service account (string) |
| `RUN_HOUR` | Hora de execução (padrão: 7) |
| `RUN_MINUTE` | Minuto de execução (padrão: 0) |
| `TZ` | Fuso horário (padrão: America/Sao_Paulo) |
| `RUN_ON_START` | Executa ao iniciar o container (`true`/`false`) |
