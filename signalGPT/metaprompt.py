import openai
import json
import requests
import random
import time

import browser_cookie3

from .__init__ import config
from .helper import save_debug_file
from .ai_providers import AI


create_char_message = '''
I am going to give you some very basic notes on a character.
Please generate the full character with this information, making up missing details if necessary. Feel free to be a bit creative and add your own touches where the notes don't provide information.
'''



def create_character_info(notes):

	messages = [{"content":create_char_message,"role":"system"},{"role":"user","content":notes}]



	completion = openai.ChatCompletion.create(
		model=config['model_meta'],
		messages=messages,
		function_call={'name':"create_character"},
		functions=[
			{
				'name': "create_character",
				'description': "Is used to create a character for an AI language model to play.",
				'parameters':{
					'type': "object",
					'required': ["prompt","name","male","handle","bio","img_prompt_keywords"],
					'properties':{
						'prompt':{
							'type': "string",
							'description': "An in-depth description of this character in second person, e.g. 'You are a x year old man', 'You enjoy watching soccer' etc. \
								You should make up missing details (e.g. expand on their character traits), but also objective facts (e.g. their full name, nationality, ethnicity, age or sex if not mentioned).\
								Include some instructions about what language to use (e.g. heavy use of slang, mixing languages, dialect, style, linguistic signature etc.)\
								Avoid introducing unprompted platitudes and moralizing phrases that could impose your own ideas on the character.\
								Only include general instructions on how to react, behave, speak etc., no specific instructions what to do right now.\
								Be creative and feel free to give the character unique traits, speech patterns, habits etc."
						},
						'name':{
							'type': "string",
							'description': "The informal name (e.g. first name, nickname, shortened name) of the character"
						},
						'male':{
							'type': "boolean",
							'description': "true if the character is male, false if they are female"
						},
						'handle':{
							'type': "string",
							'description': "A handle they might use on social media. Do not include the @ sign. It must not contain spaces or non-ASCII characters."
						},
						'bio':{
							'type': "string",
							'description': "A short tagline / bio they might use on social media (no more than 10-15 words). Depending on personality, this can contain emojis."
						},
						'img_prompt_keywords':{
							'type': "array",
							'items':{'type':"string"},
							'description': "a list of keywords to describe the character's profile picture.\
								Simply describe what can be seen in the picture in a way that could be used as a prompt for an image-generating AI.\
								Include important details like gender, ethnicity, hair color, clothes, accessories, etc.\
								Go into detail and use at least 15 keywords. Important keywords should come first."
						},
						'appearance_prompt':{
							'type': "array",
							'items':{'type':"string"},
							'description': "a list of keywords to describe the character's general looks.\
								Simply describe their features in a way that could be used as a prompt for an image-generating AI.\
								Include important details like gender, ethnicity, hair color, style etc., but not image-specific details like pose, mood, lighting.\
								Go into detail and use at least 10 keywords. Important keywords should come first."
						},
						'voice_prompt':{
							'type': "array",
							'items':{'type':"string"},
							'description': "a list of keywords to describe the character's voice.\
								Simply describe its features in a way that could be used as a prompt for a voice-generating AI."
						}
					}
				}
			}
		]

	)
	message = completion['choices'][0]['message']
	info = json.loads(message['function_call']['arguments'])

	save_debug_file('charactercreate',{'prompt':notes,'result':info})

	return info


def create_character_image(keywords,male):

	# this is kinda necessary for anydream
	# i wonder why ;)
	if male:
		negative_prompt = ['female','woman','girl']
	else:
		negative_prompt = ['male','man','boy']

	return AI['ImageGeneration'].create_image(keywords,negative_prompt,'square')
	#return create_image(keywords,negative_prompt,'square')




pick_responder_prompt = '''
I'm going to give you a chat log. Please pick who you think would be the next responder in the chat based on context, but consider that not all chat members are available to pick.
'''

def guess_next_responder(msgs,people,user):

	USE_CHANCE_MECHANIC = False
	ALLOW_LAST_RESPONDER = True

	ppl = {p.name:p for p in people}

	if msgs and (not ALLOW_LAST_RESPONDER):
		lastresponder = msgs[-1].get_author().name
		if lastresponder in ppl: ppl.pop(lastresponder)

	messages = [
		{"content":pick_responder_prompt,"role":"system"},
		{"role":"system","content":"The possible responders are: " + ', '.join(ppl.keys())},
		{"role":"user","content":"Chatlog:\n\n" + '\n'.join(msg.get_author().name + ": " + msg.display_for_textonly_model() for msg in msgs[-10:])}
	]

	#from pprint import pprint
	#pprint(messages)

	completion = openai.ChatCompletion.create(
		model=config['model_meta'],
		messages=messages,
		function_call={'name':"pick_responder"},
		functions=[
			{
				'name': "pick_responder",
				'description': "Select who should be the next responder in the group chat",
				'parameters': {
					'type': "object",
					'required': ["responder_chances" if USE_CHANCE_MECHANIC else "responder"],
					'properties':{
						'responder_chances':{
							'type': "object",
							'required': list(ppl.keys()),
							'properties':{
								p:{
									'type': "object",
									'properties':{
										'chance':{
											'type': "number",
											'description': f"Likelihood in % for {p} to be the next responder."
										},
										'reasoning':{
											'type': "string",
											'description': "A short explanation why this character is likely or unlikely to be the next responder"
										}
									}

								}
								for p in ppl
							}
						}
					} if USE_CHANCE_MECHANIC else {
						'responder':{
							'type':"string",
							'enum': list(ppl.keys()),
							'description': "The name of the selected responder. Can only be " + ', '.join(ppl.keys())
						},
						'reason':{
							'type':"string",
							'description': "A short explanation why you think this character is most likely to respond next."
						},
						'confidence':{
							'type':"number",
							'description': "a percentage value how certain you are that this will indeed be the next responder"
						}
					}
				}
			}
		])
	message = completion['choices'][0]['message']
	try:
		info = json.loads(message['function_call']['arguments'])
	except:
		print("Invalid JSON response")
		save_debug_file('responderpick',{'messages':messages,'raw_result':message})
		return None


	save_debug_file('responderpick',{'messages':messages,'result':info})

	if USE_CHANCE_MECHANIC:
		responder = max(info['responder_chances'], key=lambda x:info['responder_chances'][x]['chance'])
	else:
		responder = info['responder']

	if responder in ppl:
		return ppl[responder]
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



def create_example_chat(instructions,messages=(4,8),samples=10):

	completion = openai.ChatCompletion.create(
		model="gpt-4",
		messages=[
			{'role':'user','content':f"I'm going to send you instructions for a character. You do not actually need to follow them, instead I would like you to create {samples} examples\
			of made up conversations between this character and the first person speaker. Return your examples as a json list, with each element being a list of {messages[0]}-{messages[1]} messages between\
			this character and the speaker. Each message should be an object with the keys 'speaker' and 'message'"},
			{'role':'user','content':instructions}
		]
	)

	msg = completion['choices'][0]['message']
	return json.loads(msg['content'])
