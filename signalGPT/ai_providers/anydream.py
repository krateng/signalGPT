from . import AIProvider, Capability, singleton
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

	def create_image(self,prompt_positive,prompt_negative,format):

		if isinstance(prompt_positive,str):
			prompt_positive = [prompt_positive]
		if isinstance(prompt_negative,str):
			prompt_negative = [prompt_negative]

		prompt_negative += [
			"(worst quality:1.4)","(low quality:1.4)", "low-res", "missing fingers", "extra digit", "extra limbs", "malformed limbs", "disfigured"
		]

		prompt_positive = ",".join(prompt_positive)
		prompt_negative = ",".join(prompt_negative)

		if self.auth.get('import'):
			cj = browser_cookie3.load(domain_name=".anydream.xyz")
			cookies = {c.name:c.value for c in cj}
		else:
			cookies = {} #direct from file not supported for now

		if cookies:
			session = requests.Session()
			session.cookies.update(cookies)

			resolutions = {
				'square':(640,640),
				'portrait':(512,768),
				'landscape':(768,512)
			}

			r1 = session.post("https://www.anydream.xyz/api/a1_request",json={
				'model': "ReAL",
				'endpoint': "txt2img",
				'params':{
					'batch_size': 1,
					'cfg_scale': "7",
					'height':resolutions[format][1],
					'width': resolutions[format][0],
					'prompt':prompt_positive,
					'negative_prompt': prompt_negative,
					'seed': -1,
					'sampler_name': "DPM++ 2M Karras",
					'steps': 25
				},
				'aspectRatio': format
			})
			j = r1.json()

			if req_id := j.get('requestId'):
				pass
			else:
				save_debug_file('imageeneration',{'prompt_positive':prompt_positive,'prompt_negative':prompt_negative,'error_generate':True,'generate_request':{'json':j}})
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
						save_debug_file('imageeneration',{'prompt_positive':prompt_positive,'prompt_negative':prompt_negative,'result':img})
						return img
					else:
						print(status)
				else:
					save_debug_file('imageeneration',{'prompt_positive':prompt_positive,'prompt_negative':prompt_negative,'error_resolve':True,'result':{
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
