# test_auth_api.py
try:
    from authorizationAPI import *  # Импорт всего содержимого
    print("Успех! Файл корректно импортирован.")
except Exception as e:
    print("Ошибка:", repr(e))