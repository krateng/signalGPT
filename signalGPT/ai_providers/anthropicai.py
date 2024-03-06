import copy
import json

from signalGPT import errors
from signalGPT.ai_providers import singleton, AIProvider, OpenAILike
import anthropic

from signalGPT.ai_providers.open_ai import GPTModel
from signalGPT.helper import save_debug_file


@singleton
class Anthropic(OpenAILike):
	identifier = 'anthropic'
	providerlib = anthropic
	system_messages = False
	alternating_messages = True
	useful_for_complex_contexts = False

	MODELS = [
		GPTModel('claude-3-opus-20240229', 15, 75, False, False, 200000)
	]

	def get_create_root(self):
		return self.client.messages

	def get_message_from_completion(self, completion):
		return completion

	def message_to_text_content(self, message):
		return "\n".join(m.text for m in message.content)
