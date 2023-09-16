import openai
import json
import requests
import random

import browser_cookie3

from .__init__ import config
from .helper import save_debug_file


create_char_message = '''
I am going to give you some very basic notes on a character.
Then return to me a json mapping with the following keys:
'prompt': An in-depth description of this character in second person, e.g. 'You are a x year old man', 'You enjoy watching soccer' etc.
You should make up missing details (e.g. expand on their character traits), but also objective facts (e.g. their full name, nationality, ethnicity, age or sex if not mentioned).
Include some instructions about what language to use (e.g. heavy use of slang, mixing languages, dialect, style, emoji usage etc.)
Avoid introducing unprompted platitudes and moralizing phrases about 'breaking norms', 'challenging expectations', 'self-expression', 'empowering', 'stigma' etc.
Only include general instructions on how to react, behave, speak etc., no specific instructions what to do right now.
'name': The informal name (e.g. first name, nickname, shortened name) of the character
'male': simple boolean value, true if the character is male, false if they are female
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



	completion = openai.ChatCompletion.create(model=config['model_meta'],messages=messages)
	message = completion['choices'][0]['message']
	info = json.loads(message['content'])

	save_debug_file('charactercreate',{'prompt':notes,'result':info})

	return info


def create_character_image(prompt,keywords,male):
	negative_prompt = [
		"(worst quality:1.4)","(low quality:1.4)", "low-res", "missing fingers", "extra digit", "extra limbs", "malformed limbs", "disfigured"
	]

	# this is kinda necessary for anydream
	# i wonder why ;)
	if male:
		negative_prompt = ['female','woman','girl'] + negative_prompt
	else:
		negative_prompt = ['male','man','boy'] + negative_prompt

	# load cookies from file
	authinfo = config.get('auth',{}).get('anydream',{})
	if authinfo.get('import'):
		cj = browser_cookie3.load(domain_name=".anydream.xyz")
		cookies = {c.name:c.value for c in cj}
	else:
		cookies = {} #direct from file not supported for now

	if cookies:

		prompt_pos = prompt
		#prompt_pos = ",".join(keywords)
		prompt_neg = ', '.join(negative_prompt)

		session = requests.Session()
		session.cookies.update(cookies)

		r1 = session.post("https://www.anydream.xyz/api/a1_request",json={
			'model': "ReAL",
			'endpoint': "txt2img",
			'params':{
				'batch_size': 1,
				'cfg_scale': "7",
				'height':640,
				'width': 640,
				'prompt':prompt_pos,
				'negative_prompt': prompt_neg,
				'seed': -1,
				'sampler_name': "DPM++ 2M Karras",
				'steps': 25
			},
			'aspectRatio': "square"
		})
		j = r1.json()

		if req_id := j.get('requestId'):
			pass
		else:
			save_debug_file('imageeneration',{'prompt_positive':prompt_pos,'prompt_negative':prompt_neg,'result':j})
			return ""

		import time
		while True:

			time.sleep(2)

			r2 = session.post("https://www.anydream.xyz/api/a1_request/check",json={
				'requestId': req_id
			})
			j = r2.json()

			if status := j.get('status'):
				if status == 'success':
					img = j['images'][0]['imgUrl']
					save_debug_file('imageeneration',{'prompt_positive':prompt_pos,'prompt_negative':prompt_neg,'result':img})
					return img
			else:
				save_debug_file('imageeneration',{'prompt_positive':prompt_pos,'prompt_negative':prompt_neg,'result':{
					'json':r1.json(),
					'headers':dict(r1.headers),
					'cookies':dict(r1.cookies)
				}})
				return ""

	else:
		return ""


pick_responder_prompt = '''
I'm going to give you a chat log. Please pick who you think would be the next responder in the chat based on context.
Return your result in fully valid json with the keys:
* responder: The exact name of the responder.
* confidence: a percentage value from 0-100 (as integer, not including the % symbol) how certain you are that this will be the next responder
* reason: a short explanation why you made this choice

Please include nothing else but this json in your response.
'''

def guess_next_responder(msgs,people,user):

	ppl = {p.name:p for p in people}

	messages = [
		{"content":pick_responder_prompt,"role":"system"},
		{"role":"system","content":"The possible responders are: " + ', '.join(ppl.keys()) + f". {user.name} is not a valid pick."},
		{"role":"user","content":"Chatlog:\n\n" + '\n'.join(msg.get_author().name + ": " + msg.display_for_textonly_model() for msg in msgs[-30:])}
	]

	#from pprint import pprint
	#pprint(messages)

	completion = openai.ChatCompletion.create(model=config['model_meta'],messages=messages)
	message = completion['choices'][0]['message']
	try:
		info = json.loads(message['content'])
	except:
		print("Invalid JSON response")
		save_debug_file('responderpick',{'messages':messages,'raw_result':message['content']})
		return None


	save_debug_file('responderpick',{'messages':messages,'result':info})

	if info['responder'] in ppl:
		return ppl[info['responder']]
	else:
		return None


summarize_prompt = '''
Please analzye the above chat and what happened during it.
Summarize important implications in terms of character development or changes in relationship dynamics.
Do not include every single thing that happened. Do not describe all steps that lead to it, only the final outcomes.
Do not list people acknowledging something or talking about something, only list final changes in their dynamics.
Be very concise. Bullet points are sufficent.
Do not add any meta information about your result.
'''

summarize_prompt_directed = '''
Focus on changes that affect the character {partner.name}.
Write your summary in the form of information bits for a chatbot who is supposed to act as {partner.name} and needs to be updated on their knowledge, behavious, character, relationships etc. based on this chat.
Speak in second person to the chatbot {partner.name}.
Do not give any general chatbot instructions, only tell them what new information they need to know based on this chat.
Do not give advice or instructions. Simpy inform about relevant changes.
'''

summarize_prompt_external = '''
Begin your response with "In another chat, ..."
'''

summarize_prompt_internal = '''
Begin your response with "During the chat so far, ..."
'''

def summarize_chat(msgs,perspective=None,external=False):

	messages = [
		{
			'role':'user',
			'content':msg.get_author().name + ": " + msg.display_for_textonly_model()
		}
		for msg in msgs
	] + [
		{
			'role':'user',
			'content':summarize_prompt + (summarize_prompt_directed.format(partner=perspective) if perspective else "") + (summarize_prompt_external if external else summarize_prompt_internal)
		}
	]


	completion = openai.ChatCompletion.create(model=config['model_meta'],messages=messages)
	msg = completion['choices'][0]['message']
	content = msg['content']

	save_debug_file('summarize',{'messages':messages,'result':content})

	return content
