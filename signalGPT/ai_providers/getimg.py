import requests

from . import AIProvider, Format, singleton, ImageGenerateProvider
from ..helper import save_debug_file

@singleton
class GetImg(ImageGenerateProvider):
	identifier = 'getimg'

	def create_image(self, keyword_prompt: list, keyword_prompt_negative: list, fulltext_prompt: str, imageformat: Format):

		session = requests.Session()

		session.headers.update({
			'Authorization': f"Bearer {self.config['apikey']}"
		})

		payload = {
			'model':"stable-diffusion-xl-v1-0",
			'prompt': ", ".join(keyword_prompt),
			'negative_prompt': ", ".join(keyword_prompt_negative)
		}

		r1 = session.post("https://api.getimg.ai/v1/stable-diffusion-xl/text-to-image",json=payload)

		result = r1.json()


		try:
			save_debug_file('imageeneration',{'prompt_positive':keyword_prompt,'prompt_negative':keyword_prompt_negative})
			return 'data:image/png;base64,' + result['image']
		except:
			save_debug_file('imageeneration',{'prompt_positive':keyword_prompt,'prompt_negative':keyword_prompt_negative,'response':result,'payload':payload})