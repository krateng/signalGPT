import openai
import json
import requests

import browser_cookie3

from .__init__ import config


create_char_message = '''
I am going to give you some very basic notes on a character.
Then return to me a json mapping with the following keys:
'prompt': An in-depth description of this character in second person, e.g. 'You are a x year old man', 'You enjoy watching soccer' etc.
You should make up missing details (e.g. expand on their character traits), but also objective facts (e.g. their full name, nationality, ethnicity, age or sex if not mentioned).
Include some instructions about what language to use (e.g. heavy use of slang, mixing languages, dialect, style, emoji usage etc.)
Avoid introducing unprompted platitudes and moralizing phrases about 'breaking norms', 'challenging expectations', 'self-expression', 'empowering', 'stigma' etc.
Only include general instructions on how to react, behave, speak etc., no specific instructions what to do right now.
'name': The informal name (e.g. first name, nickname, shortened name) of the character
'handle': A handle they might use on social media. Do not include the @ sign. It must not contain spaces or non-ASCII characters.
'bio': A short biography they might use on social media (no more than 15-20 words)
'img_prompt': a description of the character's profile picture.
Don't write in second person, simply describe what can be seen in the picture in a way that could be used as a prompt for an image-generating AI.
Describe important details like gender, ethnicity, hair color, clothes, accessories, etc.
Be concise and list important keywords
'img_prompt_keywords': a json list of keywords to describe the character's profile picture from above.
Use at least 10 keywords, but no more than 100

Use these exact keys. Do not add anything else to your output (like acknowledging the task or reminding me that this is a fictional character etc.) The full post must be valid json.
'''



def create_character_info(notes):

	messages = [{"content":create_char_message,"role":"system"},{"role":"user","content":notes}]

	print("Generating character...")
	print("Prompt: " + notes)
	print()

	completion = openai.ChatCompletion.create(model=config['model'],messages=messages)
	message = completion['choices'][0]['message']
	info = json.loads(message['content'])
	return info


def create_character_image(prompt,keywords):
	negative_prompt = [
		"(worst quality:1.4)","(low quality:1.4)", "low-res", "missing fingers", "extra digit", "extra limbs", "malformed limbs", "disfigured"
	]

	# load cookies from file
	cookies = config.get('auth',{}).get('anydream',{})
	# overwrite them if we can
	if import_src := config.get('auth',{}).get('import_from'):


		import_func = {
			'brave': browser_cookie3.brave
		}
		# update
		cj = import_func[import_src]()
		cookies = {c.name:c.value for c in cj if "anydream" in c.domain}

	if cookies:

		used_prompt = prompt
		#used_prompt = ",".join(keywords)

		print("Getting image from anydream...")
		print("Prompt: " + used_prompt)

		r = requests.post("https://www.anydream.xyz/api/a1_request",json={
			'model': "ReAL",
			'endpoint': "txt2img",
			'params':{
				'batch_size': 1,
				'cfg_scale': "7",
				'height':640,
				'width': 640,
				'prompt':used_prompt,
				'negative_prompt': ', '.join(negative_prompt),
				'seed': -1,
				'sampler_name': "DPM++ 2M Karras",
				'steps': 25
			},
			'aspectRatio': "square"
		},cookies=cookies).json()

		if req_id := r.get('requestId'):
			pass
		else:
			print(r)
			print()
			return ""

		import time
		while True:

			time.sleep(2)

			r = requests.post("https://www.anydream.xyz/api/a1_request/check",json={
				'requestId': req_id
			},cookies=cookies).json()

			if status := r.get('status'):
				if status == 'success':
					print()
					return r['images'][0]['imgUrl']
			else:
				print(r)
				print()
				return ""

	else:
		print()
		return ""
