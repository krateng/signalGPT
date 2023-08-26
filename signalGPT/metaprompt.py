import openai
import json
import requests

from .__init__ import config






def create_character_info(notes):
	base_messages = [
		'''I am going to give you some very basic notes on a character.
		Then return to me a json mapping with the following keys:
		'prompt': An in-depth description of this character in second person, e.g. 'You are a x year old man', 'You enjoy watching soccer' etc.
		You should make up missing details (e.g. expand on their character traits), but also objective facts (e.g. their full name, nationality, ethnicity, age or sex if not mentioned).
		Include some instructions about what language to use (e.g. heavy use of slang, mixing languages, dialect, style, emoji usage etc.)
		Avoid introducing unprompted platitudes and moralizing phrases about 'breaking norms', 'challenging expectations', 'self-expression', 'empowering', 'stigma' etc.
		Only include general instructions on how to react, behave, speak etc., no specific instructions what to do right now.
		'name': The informal name (e.g. first name, nickname, shortened name) of the character
		'handle': A handle they might use on social media. Do not include the @ sign. It must not contain spaces or non-ASCII characters.
		'bio': A short biography they might use on social media (not more than 20 words)
		'img_prompt': a description of the character's profile picture.
		Don't write in second person, simply describe what can be seen on the picture in a way that could be used as a prompt for an image generating AI.
		Describe important details like hair color, ethnicity, clothes, accessories, eye color, etc.
		Be concise and list important keywords

		Use these exact keys. Do not add anything else to your output (like acknowledging the task or reminding me that this is a fictional character etc.) The full post must be valid json.
		 '''
	]
	messages = [{"content":msg,"role":"system"} for msg in base_messages] + [{"role":"user","content":notes}]

	print("Generating character...")
	print("Prompt: " + notes)

	completion = openai.ChatCompletion.create(model=config['model'],messages=messages)
	message = completion['choices'][0]['message']
	info = json.loads(message['content'])
	return info


def create_character_image(prompt):
	negative_prompt = [
		"(worst quality:1.4)","(low quality:1.4)", "low-res", "missing fingers", "extra digit", "extra limbs", "malformed limbs", "disfigured"
	]

	if cookie := config.get('auth',{}).get('anydream',{}).get('cookie'):

		print("Getting image from anydream...")
		print("Prompt: " + prompt)

		r = requests.post("https://www.anydream.xyz/api/a1_request",json={
			'model': "ReAL",
			'endpoint': "txt2img",
			'params':{
				'batch_size': 1,
				'cfg_scale': "7",
				'height':1000,
				'width': 1000,
				'prompt':prompt,
				'negative_prompt': ', '.join(negative_prompt),
				'seed': -1,
				'sampler_name': "DPM++ 2M Karras",
				'steps': 25
			},
			'aspectRatio': "square"
		},headers={
			'Cookie':cookie
		}).json()

		if req_id := r.get('requestId'):
			pass
		else:
			print(r)
			return ""

		import time
		while True:

			time.sleep(2)

			r = requests.post("https://www.anydream.xyz/api/a1_request/check",json={
				'requestId': req_id
			},headers={
				'Cookie':cookie
			}).json()

			if status := r.get('status'):
				if status == 'success':
					return r['images'][0]['imgUrl']
			else:
				print(r)
				return ""

	else:
		return ""
