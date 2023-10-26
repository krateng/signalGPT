from . import AIProvider, Capability, singleton
import openai


@singleton
class OpenAI(AIProvider):
	capabilities = [
		Capability.ImageGeneration
	]
	identifier = 'openai'

	def create_image(self, keyword_prompt, keyword_prompt_negative, fulltext_prompt, imageformat):

		result = openai.Image.create(
			prompt=fulltext_prompt,
			n=1,
			size="1024x1024"
		)

		img = result['data'][0]['url']

		return img
