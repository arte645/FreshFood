1. Поставить виртуальное окружение
2. Установить библиотеки из requirements.txt
3. Запуск gatewayAPI(микросервис, который перенаправляет на другие микросервисы, сам ничего не выполняет. На фронте нужно будет обращаться именно к нему): uvicorn gatewayAPI:app --host localhost --port 443
4. Запуск authorizationAPI(микросервис для авторизации пользователя): py authorizationAPI
5. Запуск databaseAPI(микросервис для работы с бд): py databaseAPI.py
