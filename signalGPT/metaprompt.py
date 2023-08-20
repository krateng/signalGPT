import openai
import json

from .__init__ import config






def create_character_info(notes):
	base_messages = [
		'''I am going to give you some very basic notes on a character. You should make up missing details (e.g. expand on their character traits), but also objective facts (e.g. their full name, nationality, ethnicity, age or sex if not mentioned).
		Please output your response in second person, e.g. 'You are a x year old man', 'You enjoy watching soccer' etc.
		Include some instructions about what language to use (e.g. heavy use of slang, mixing languages, dialect, style, emoji usage etc.)
		Be somewhat concise.
		Avoid introducing unprompted platitudes and moralizing phrases about 'breaking norms', 'challenging expectations', 'self-expression', 'empowering', 'stigma' etc.''',
		"Do not add anything else to your output (like acknowledging the task or reminding me that this is a fictional character etc.)"
	]
	messages = [{"content":msg,"role":"system"} for msg in base_messages] + [{"role":"user","content":notes}]
	completion = openai.ChatCompletion.create(model=config['model'],messages=messages)
	message = completion['choices'][0]['message']
	messages.append(message)
	prompt = message['content']
	
	extra_messages = [
		'''Now give me the informal name (e.g. only prename) of this character, as well as a handle they might use on social media, and a very short bio text (fewer than 15 words) they might use.
		Please output them in valid json with the exact key names 'name', 'handle' and 'bio'. The handle should not include the @ sign and not contain spaces or non-ASCII symbols.
		
		Do not add anything else to your output.'''
	]
	messages += [{"role":"user","content":msg} for msg in extra_messages]
	completion = openai.ChatCompletion.create(model=config['model'],messages=messages)
	message = completion['choices'][0]['message']
	info = json.loads(message['content'])
	
	return {'prompt':prompt,'name':info['name'],'handle':info['handle'],'bio':info['bio']}
