_AI_CONFIG = {
    'Groq': {
        'env': 'GROQ_API_KEY',
        'site': 'https://console.groq.com/keys',
        'models': {
            'muse-spark-v1': {'ctx': '256k', 'rpm': '30', 'rpd': '1440', 'desc': 'Ultra-fast inference (Meta MSL)'},
            'muse-spark-lite': {'ctx': '128k', 'rpm': '60', 'rpd': '5000', 'desc': 'Sub-second response (Meta MSL)'},
            'llama-4-70b': {'ctx': '1M', 'rpm': '20', 'rpd': '1000', 'desc': 'High reasoning Scout (Meta)'},
            'llama-4-8b': {'ctx': '128k', 'rpm': '100', 'rpd': '10k', 'desc': 'Instant response Maverick (Meta)'},
            'llama-3.3-70b-versatile': {'ctx': '128k', 'rpm': '30', 'rpd': '1000', 'desc': 'Proven versatile Llama 3'},
            'mixtral-8x7b-32768': {'ctx': '32k', 'rpm': '60', 'rpd': '3000', 'desc': 'Classic MoE architecture'}
        }
    },
    'OpenAI': {
        'env': 'OPENAI_API_KEY',
        'site': 'https://platform.openai.com/api-keys',
        'models': {
            'gpt-5.4-pro': {'ctx': '1M', 'rpm': '10', 'rpd': '100', 'desc': 'Omni flagship 2026'},
            'gpt-5.4-mini': {'ctx': '128k', 'rpm': '50', 'rpd': '2000', 'desc': 'Fast, efficient generation'},
            'gpt-5.4-nano': {'ctx': '32k', 'rpm': '200', 'rpd': '50k', 'desc': 'On-device scale specialized'},
            'gpt-5.4-cyber': {'ctx': '512k', 'rpm': '5', 'rpd': '50', 'desc': 'Security optimized reasoning'},
            'gpt-4o': {'ctx': '128k', 'rpm': '60', 'rpd': '3000', 'desc': 'Legacy Omni flagship'},
            'o1-preview': {'ctx': '128k', 'rpm': '5', 'rpd': '50', 'desc': 'Early reasoning model'}
        }
    },
    'Google': {
        'env': 'GOOGLE_API_KEY',
        'site': 'https://aistudio.google.com/app/apikey',
        'models': {
            'gemini-3.1-pro': {'ctx': '2M', 'rpm': '5', 'rpd': '50', 'desc': 'Deep reasoning leader'},
            'gemini-3.1-flash': {'ctx': '1M', 'rpm': '15', 'rpd': '1500', 'desc': 'High-volume multimodal'},
            'gemini-3.1-deep-think': {'ctx': '512k', 'rpm': '2', 'rpd': '20', 'desc': 'Mathematical/Scientific focus'},
            'gemini-3.1-flash-lite': {'ctx': '256k', 'rpm': '60', 'rpd': '10k', 'desc': 'Extreme low latency'},
            'gemini-2.5-pro': {'ctx': '2M', 'rpm': '10', 'rpd': '100', 'desc': 'Stable 2.5 era flagship'},
            'gemini-2.5-flash': {'ctx': '1M', 'rpm': '30', 'rpd': '3000', 'desc': 'Proven speed flagship'}
        }
    },
    'DeepSeek': {
        'env': 'DEEPSEEK_API_KEY',
        'site': 'https://platform.deepseek.com/api_keys',
        'models': {
            'deepseek-v3': {'ctx': '128k', 'rpm': '60', 'rpd': '3000', 'desc': 'Current flagship (V3.2)'},
            'deepseek-chat': {'ctx': '64k', 'rpm': '100', 'rpd': '10k', 'desc': 'Proven chat model'},
            'deepseek-reasoner': {'ctx': '32k', 'rpm': '10', 'rpd': '200', 'desc': 'Advanced R1 reasoning'}
        }
    }
}
