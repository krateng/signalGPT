from . import AIProvider, Capability, Format, singleton
from ..helper import save_debug_file

import browser_cookie3
import requests
import json
import time


@singleton
class Anydream(AIProvider):
	capabilities = [
		Capability.ImageGeneration
	]
	identifier = 'anydream'

	def create_image(self, keyword_prompt: list, keyword_prompt_negative: list, fulltext_prompt: str, imageformat: Format):

		#if isinstance(prompt_positive,str):
		#	prompt_positive = [prompt_positive]
		#if isinstance(prompt_negative,str):
		#	prompt_negative = [prompt_negative]

		keyword_prompt_negative += [
			"(worst quality:1.4)","(low quality:1.4)", "low-res", "missing fingers", "extra digit", "extra limbs", "malformed limbs", "disfigured"
		]

		prompt_positive = ",".join(keyword_prompt)
		prompt_negative = ",".join(keyword_prompt_negative)

		if self.auth.get('import'):
			cj = browser_cookie3.load(domain_name=".anydream.xyz")
			cookies = {c.name: c.value for c in cj}
		else:
			cookies = {}  # direct from file not supported for now

		if cookies:
			session = requests.Session()
			session.cookies.update(cookies)

			resolutions = {
				Format.Square: (640, 640, 'square'),
				Format.Portrait: (512, 768, 'portrait'),
				Format.Landscape: (768, 512, 'landscape')
			}

			r1 = session.post("https://www.anydream.xyz/api/a1_request",json={
				'model': "ReAL",
				'endpoint': "txt2img",
				'params':{
					'batch_size': 1,
					'cfg_scale': "7",
					'height': resolutions[imageformat][1],
					'width': resolutions[imageformat][0],
					'prompt': keyword_prompt,
					'negative_prompt': keyword_prompt_negative,
					'seed': -1,
					'sampler_name': "DPM++ 2M Karras",
					'steps': 25
				},
				'aspectRatio': resolutions[imageformat][2]
			})
			j = r1.json()

			if req_id := j.get('requestId'):
				pass
			else:
				save_debug_file('imageeneration',{'prompt_positive':keyword_prompt,'prompt_negative':keyword_prompt_negative,'error_generate':True,'generate_request':{'json':j}})
				return ""


			while True:

				time.sleep(2)

				r2 = session.post("https://www.anydream.xyz/api/a1_request/check",json={
					'requestId': req_id
				})
				j = r2.json()

				if status := j.get('status'):
					if status == 'requested':
						pass
					elif status == 'success':
						img = j['images'][0]['imgUrl']
						save_debug_file('imageeneration',{'prompt_positive':keyword_prompt,'prompt_negative':keyword_prompt_negative,'result':img})
						return img
					else:
						print(status)
				else:
					save_debug_file('imageeneration',{'prompt_positive':keyword_prompt,'prompt_negative':keyword_prompt_negative,'error_resolve':True,'result':{
						'generate_request':{
							'json':r1.json(),
							'headers':dict(r1.headers),
							'cookies':dict(r1.cookies)
						},
						'resolve_request':{
							'json':r2.json(),
							'headers':dict(r2.headers),
							'cookies':dict(r2.cookies)
						}
					}})
					return ""

		else:
			return ""
