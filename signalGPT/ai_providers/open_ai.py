import copy
import json
from collections import namedtuple

from . import AIProvider, singleton, OpenAILike, ResponderPickProvider, CharacterCreateProvider, \
	ImageGenerateProvider
import openai

from .. import errors
from ..helper import save_debug_file


GPTModel = namedtuple('GPTModel', ['identifier', 'cost_input', 'cost_output', 'vision_capable', 'functions', 'context_window'])
# cost is dollar per 1M token




@singleton
class OpenAI(OpenAILike, ResponderPickProvider, CharacterCreateProvider, ImageGenerateProvider):
	identifier = 'openai'
	providerlib = openai
	system_messages = True
	user_names = True

	MODELS = [
		GPTModel('gpt-3.5-turbo-0125', 0.5, 1.2, False, False, 16385),
		GPTModel('gpt-4', 30, 60, False, True, 8192),
		GPTModel('gpt-4-32k', 60, 120, False, True, 32768),
		GPTModel('gpt-4-1106-preview', 10, 30, False, True, 128000),
		GPTModel('gpt-4-vision-preview', 10, 30, True, False, 128000),
		GPTModel('gpt-4-0125-preview', 10, 30, False, True, 128000),
		GPTModel('gpt-4-turbo-2024-04-09', 10, 30, True, True, 128000),
		GPTModel('gpt-4o', 5, 15, True, True, 128000),
		GPTModel('gpt-4o-mini', 0.15, 0.6, True, True, 128000)
	]

	def create_image(self, keyword_prompt, keyword_prompt_negative, fulltext_prompt, imageformat):

		self.init_client()

		result = self.client.images.generate(
			prompt=fulltext_prompt,
			n=1,
			size="1024x1024"
		)

		img = result['data'][0]['url']

		return img

	def guess_next_responder(self,msgs,validpeople):

		self.init_client()


		pick_responder_prompt = '''
			I'm going to give you a chat log.
			Please pick who you think would be the next responder in the chat based on context,
			but consider that not all chat members are available to pick.
			Return the handle of your picked user without the @.
		'''.replace('\t','')

		USE_CHANCE_MECHANIC = False


		messages = [
			{"content":pick_responder_prompt,"role":"system"},
			{"role":"system","content":"The possible responders are: " + ', '.join(f"@{p.handle} ({p.name})" for p in validpeople)},
			{"role":"user","content":"Chatlog:\n\n" + '\n'.join("@" + msg.get_author().handle + ": " + msg.display_for_model() for msg in msgs[-10:])}
		]

		#from pprint import pprint
		#pprint(messages)

		completion = self.client.chat.completions.create(
			model=self.config['model_meta'],
			messages=messages,
			tool_choice={'type':'function','function':{'name':"pick_responder"}},
			tools=[
				{
					'type':'function',
					'function':{
						'name': "pick_responder",
						'description': "Select who should be the next responder in the group chat",
						'parameters': {
							'type': "object",
							'required': ["responder_chances"] if USE_CHANCE_MECHANIC else ["responder","alternative_responder"],
							'properties':{
								'responder_chances':{
									'type': "object",
									'required': [p.handle for p in validpeople],
									'properties':{
										p.handle:{
											'type': "object",
											'properties':{
												'chance':{
													'type': "number",
													'description': f"Likelihood in % for @{p.handle} to be the next responder."
												},
												'reasoning':{
													'type': "string",
													'description': "A short explanation why this character is likely or unlikely to be the next responder"
												}
											}

										}
										for p in validpeople
									}
								}
							} if USE_CHANCE_MECHANIC else {
								'responder':{
									'type':"string",
									'enum': [p.handle for p in validpeople],
									'description': "The handle of the selected responder. Can only be " + ', '.join(p.handle for p in validpeople)
								},
								'reason':{
									'type':"string",
									'description': "A short explanation why you think this character is most likely to respond next."
								},
								'alternative_responder':{
									'type':"string",
									'enum': [p.handle for p in validpeople],
									'description': "An alternative pick for the next most likely responder."
								}
							}
						}
					}
				}

			])
		message = completion.choices[0].message
		try:
			info = json.loads(message.tool_calls[0].function.arguments)
		except:
			print("Invalid JSON response")
			save_debug_file('responderpick',{'messages':messages,'raw_result':message.model_dump()})
			return None


		save_debug_file('responderpick',{'messages':messages,'result':info})

		if USE_CHANCE_MECHANIC:
			responder = max(info['responder_chances'], key=lambda x:info['responder_chances'][x]['chance'])
		else:
			responder = info['responder'].replace("@","")
			if responder not in [p.handle for p in validpeople]:
				responder = info['alternative_responder']

		if responder in [p.handle for p in validpeople]:
			return [p for p in validpeople if p.handle == responder][0]
		else:
			return None

	def create_character_info(self,notes):

		create_char_message = '''
			I am going to give you some very basic notes on a character.
			Please generate the full character with this information, making up missing details if necessary. Feel free to be a bit creative and add your own touches where the notes don't provide information.
		'''.replace('\t','')

		messages = [{"content":create_char_message,"role":"system"},{"role":"user","content":notes}]

		self.init_client()

		completion = self.client.chat.completions.create(
			model=self.config['model_meta'],
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
								'description': "A short tagline / bio they might use on social media (no more than 10-15 words). Make sure this isn't just some corporate sounding self-description,\
									but a very personal, self-selected tagline that reflects their personality. It sounding believable is much more important than containing all the information\
									about the character."
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
		message = completion.choices[0].message
		info = json.loads(message.function_call.arguments)

		save_debug_file('charactercreate',{'prompt':notes,'result':info})

		return info
