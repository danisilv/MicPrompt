# MicPrompt — Ditado e Colagem Automática (Windows)

Transcreva sua fala em texto usando modelos da OpenAI e cole automaticamente no app ativo com um atalho global. O app roda em background com ícone na bandeja do Windows.

## Recursos
- Atalho para iniciar/parar a gravação e transcrever.
- Colagem automática: copia o texto e envia `Ctrl+V` para a janela ativa.
- Fallback de modelo: tenta `gpt-4o-mini-transcribe` e cai para `whisper-1`.
- Seleção de microfone por nome parcial (ex.: "Logi", "G733").
- Limite de gravação configurável (padrão: 180s).
- Ícone de bandeja com “Listar microfones” e “Sair”.

## Requisitos
- Windows 10/11
- Python 3.9+
- Variável de ambiente `OPENAI_API_KEY`
- Dependências Python (vide `requirements.txt`)

## Instalação
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
# Caso necessário
pip install soundfile pyperclip

# Configure a chave da OpenAI (reabra o terminal após):
setx OPENAI_API_KEY "sua_chave_aqui"
```

## Execução
- Com console (útil para logs/listar microfones):
  ```powershell
  python main.py
  ```
- Em background (sem console, com ícone na bandeja):
  ```
  run.bat
  ```

## Atalhos
- Iniciar/parar gravação: `Ctrl+Alt+Space`
- Cancelar (descarta áudio): `Ctrl+Alt+Backspace`
- Listar microfones: `F10` (saída no console)

## Configuração Rápida (em `main.py`)
- `INPUT_DEVICE_NAME`: fragmento do nome do microfone.
- `SAMPLE_RATE`, `CHANNELS`, `DTYPE`: parâmetros de captura (padrões: 16000, 1, int16).
- `PRIMARY_STT_MODEL`: por padrão `gpt-4o-mini-transcribe` (ou defina `STT_MODEL`).
- `FALLBACK_STT_MODEL`: `whisper-1`.
- `ADD_TRAILING_SPACE` / `ADD_TRAILING_NEWLINE`: adiciona espaço/quebra ao final.
- `MAX_RECORD_SECONDS`: duração máxima (padrão 180s).

## Como funciona
1. Enquanto gravando, o áudio é acumulado e salvo temporariamente em `%TEMP%/dictate.wav`.
2. O arquivo é enviado à API de transcrição e removido ao final.
3. O texto é colocado na área de transferência, colado com `Ctrl+V` e a área de transferência original é restaurada.

## Dicas
- Para descobrir o nome do dispositivo, rode com console e use `F10` ou o item “Listar microfones” do ícone (a listagem aparece no console).
- Para iniciar com o Windows, crie um atalho para `run.bat` na pasta de Inicialização do Windows.

## Resolução de Problemas
- "OPENAI_API_KEY não configurada": defina a variável e reabra o terminal.
- Nada é colado: garanta foco em um campo de texto e permissões do `keyboard`.
- Microfone errado: ajuste `INPUT_DEVICE_NAME` ou remova para usar padrão.
- Áudio vazio: verifique o microfone e volume de entrada.

