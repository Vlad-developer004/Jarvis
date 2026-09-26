_AI_CONFIG = {
    'Groq': {
        'id':   'groq',
        'icon': '⚡',
        'env':  'GROQ_API_KEY',
        'site': 'https://console.groq.com/keys',
    },
    'OpenAI': {
        'id':   'openai',
        'icon': '◆',
        'env':  'OPENAI_API_KEY',
        'site': 'https://platform.openai.com/api-keys',
    },
    'Google': {
        'id':   'google',
        'icon': '♊',
        'env':  'GOOGLE_API_KEY',
        'site': 'https://aistudio.google.com/app/apikey',
    },
    'DeepSeek': {
        'id':   'deepseek',
        'icon': '◎',
        'env':  'DEEPSEEK_API_KEY',
        'site': 'https://platform.deepseek.com/api_keys',
    },
    'Anthropic': {
        'id':   'anthropic',
        'icon': '✦',
        'env':  'ANTHROPIC_API_KEY',
        'site': 'https://console.anthropic.com/settings/keys',
    },
    'OpenRouter': {
        'id':   'openrouter',
        'icon': '⬡',
        'env':  'OPENROUTER_API_KEY',
        'site': 'https://openrouter.ai/keys',
    },
    'Local': {
        # Self-hosted OpenAI-compatible server — Ollama, llama.cpp's
        # llama-server, TabbyAPI. No fixed 'site' (nothing to sign up for);
        # the server address is configured in the UI instead of an API key.
        'id':   'local',
        'icon': '🖥',
        'env':  'LOCAL_LLM_API_KEY',
        'site': '',
    },
}
