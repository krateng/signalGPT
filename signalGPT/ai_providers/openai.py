from . import AIProvider, singleton

@singleton
class OpenAI(AIProvider):
	capabilities = [
	]
	identifier = 'openai'
