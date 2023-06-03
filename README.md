# How to run this bot

Build and deploy function to yandex cloud:

```bash
npm run deploy
```

Set TelegramBot web-hook to new destination:

```bash
source .env
export BOT_URL=https://d5d95olvpmjkrqa0imj0.apigw.yandexcloud.net/telegraf
export SET_WEBHOOK_URL="https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${BOT_URL}"
echo $SET_WEBHOOK_URL
curl $SET_WEBHOOK_URL
```

How to unset hook:

```bash
curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url="
```
