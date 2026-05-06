# SELEZNEV Local Share — интернет-доступ без покупки домена

## Быстрый запуск

1. Скопируйте файл `start_internet.bat` в папку проекта рядом с `app.py`.
2. Запустите `start_internet.bat`.

Откроются два окна:

1. Локальный сервер SELEZNEV Local Share
2. Cloudflare Tunnel

Во втором окне появится адрес вида:

```text
https://example-example.trycloudflare.com
```

Это временный интернет-адрес.

## Важно

Адрес `trycloudflare.com` временный. Он меняется при каждом новом запуске tunnel.

Для постоянного адреса нужен:
- собственный домен
- или другой сервис с постоянным адресом

## Безопасность

Доступ через интернет защищён логином/паролем приложения.

Обязательно:
- поменять пароль admin
- не использовать пароль 1234
- не публиковать ссылку публично

## Если winget не установил cloudflared

Скачайте cloudflared вручную:

https://github.com/cloudflare/cloudflared/releases/latest

Нужен файл:

```text
cloudflared-windows-amd64.exe
```

Переименуйте его в:

```text
cloudflared.exe
```

Положите рядом с `start_internet.bat`.

Потом снова запустите:

```text
start_internet.bat
```