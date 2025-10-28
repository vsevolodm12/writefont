# Решение проблемы с Python 3.14

Python 3.14 слишком новый и не поддерживается pydantic-core. 

## Решение 1: Установить Python 3.12 (рекомендуется)

```bash
# Установить через Homebrew
brew install python@3.12

# Пересоздать виртуальное окружение
cd ~/Desktop/consp_bot
rm -rf venv
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Решение 2: Использовать pyenv

```bash
# Установить pyenv
brew install pyenv

# Установить Python 3.12
pyenv install 3.12.7

# Пересоздать venv
cd ~/Desktop/consp_bot
rm -rf venv
pyenv local 3.12.7
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Решение 3: Попробовать установить зависимости без pydantic

Можно попробовать установить более старую версию aiogram без pydantic, но это может привести к проблемам совместимости.

