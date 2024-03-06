import openai
import json
import requests
import random
import time

import browser_cookie3

from .__init__ import config
from .helper import save_debug_file



# TODO redo this whole import mess wtf


def create_character_info(notes):

	from .ai_providers import AI, Format

	return AI['CharacterCreation'].create_character_info(notes)


def create_character_image(keywords,male):

	from .ai_providers import AI, Format

	# this is kinda necessary for anydream
	# i wonder why ;)
	if male:
		negative_prompt = ['female','woman','girl']
	else:
		negative_prompt = ['male','man','boy']

	return AI['ImageGeneration'].create_image(keyword_prompt=keywords,keyword_prompt_negative=negative_prompt,fulltext_prompt="",imageformat=Format.Square)
	#return create_image(keywords,negative_prompt,'square')






def guess_next_responder(msgs,people,user):

	from .ai_providers import AI, Format

	ALLOW_LAST_RESPONDER = True

	validpeople = [p for p in people]

	if msgs and (not ALLOW_LAST_RESPONDER):
		lastresponder = msgs[-1].get_author()
		validpeople = [p for p in validpeople if p is not lastresponder]

	return AI['ResponderPick'].guess_next_responder(msgs,validpeople)


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
			'content':msg.get_author().name + ": " + msg.display_for_model()
		}
		for msg in msgs
	] + [
		{
			'role':'user',
			'content':summarize_prompt + (summarize_prompt_directed.format(partner=perspective) if perspective else "") + (summarize_prompt_external if external else summarize_prompt_internal)
		}
	]


	completion = openai.chat.completions.create(model=config['model_meta'],messages=messages)
	msg = completion['choices'][0]['message']
	content = msg['content']

	save_debug_file('summarize',{'messages':messages,'result':content})

	return content



def create_example_chat(instructions,messages=(4,8),samples=10):

	completion = openai.chat.completions.create(
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
