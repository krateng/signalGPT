import copy
import json
from collections import namedtuple

from . import AIProvider, Capability, singleton
import openai

from ..helper import save_debug_file


GPTModel = namedtuple('GPTModel',['identifier','cost_input','cost_output','vision_capable','functions','context_window'])

MODELS = [
	GPTModel('gpt-3.5-turbo-16k',3,4,False,True,16385),
	GPTModel('gpt-4',30,60,False,True,8192),
	GPTModel('gpt-4-32k',60,120,False,True,32768),
	GPTModel('gpt-4-1106-preview',10,30,False,True,128000),
	GPTModel('gpt-4-vision-preview',10,30,True,False,128000),
]



@singleton
class OpenAI(AIProvider):
	capabilities = [
		Capability.ImageGeneration,
		Capability.ChatResponse
	]
	identifier = 'openai'

	def is_vision_capable(self):
		if 'model_vision' in self.config:
			model = [m for m in MODELS if m.identifier == self.config['model_vision']][0]
		else:
			model = [m for m in MODELS if m.identifier == self.config['model']][0]
		return model.vision_capable

	def create_image(self, keyword_prompt, keyword_prompt_negative, fulltext_prompt, imageformat):

		result = openai.Image.create(
			prompt=fulltext_prompt,
			n=1,
			size="1024x1024"
		)

		img = result['data'][0]['url']

		return img

	def respond_chat(self, chat, messagelist, allow_functioncall=True):

		client = openai.OpenAI(
			api_key=self.config['apikey']
		)

		if any(isinstance(m['content'],list) for m in messagelist[-7:]):
			model = [m for m in MODELS if m.identifier == self.config['model_vision']][0]
			print('use vision model!')
			messagelist_for_log = []
			for m in messagelist:
				logm = copy.deepcopy(m)
				try:
					logm['content'][0]['image_url']['url'] = logm['content'][0]['image_url']['url'][:30] + "...(shortened)"
				except:
					pass
				messagelist_for_log.append(logm)

		else:
			model = [m for m in MODELS if m.identifier == self.config['model']][0]
			messagelist_for_log = messagelist

		funcargs = {
			'tools':[{'type':'function','function':f['lazyschema']} for f in chat.get_ai_accessible_funcs().values()],
			'tool_choice':('auto' if allow_functioncall else 'none')
		} if model.functions else {}

		completion = client.chat.completions.create(
			model=model.identifier,
			messages=messagelist,
			**funcargs
		)

		total_cost = 0

		msg = completion.choices[0].message
		cost = completion.usage
		total_cost += model.cost_input * cost.prompt_tokens
		total_cost += model.cost_output * cost.completion_tokens

		text_content = msg.content
		toolcalls = msg.tool_calls

		if toolcalls:
			funccall = toolcalls[0]

			# ai indicated it wants to use that function, so we now provide it with the full signature
			called_func = chat.get_ai_accessible_funcs()[funccall.function.name]
			completion = client.chat.completions.create(
				model=model.identifier,
				messages=messagelist,
				tools=[{'type': 'function', 'function': called_func['schema']}],
				tool_choice={'type': 'function', 'function': {'name': funccall.function.name}}
			)
			msg2 = completion.choices[0].message
			cost = completion.usage
			total_cost += model.cost_input * cost.prompt_tokens
			total_cost += model.cost_output * cost.completion_tokens

			funccall2 = msg2.tool_calls[0]
			args = json.loads(funccall2.function.arguments)

			if called_func['lazy']:
				actual_functions = called_func['func'](self=chat)
				# this is a func that has no args yet to save tokens
				# once the AI decides to call it, we ask it again, this time with details

				completion = client.chat.completions.create(
					model=model.identifier,
					messages=messagelist,
					tools=[{'type': 'function', 'function': f['schema']} for f in actual_functions.values()]
				)
				msg3 = completion.choices[0].message
				cost = completion.usage

				total_cost += model.cost_input * cost.prompt_tokens
				total_cost += model.cost_output * cost.completion_tokens

				funccall3 = msg3.tool_calls[0]
				args = json.loads(funccall3.function.arguments)


				save_debug_file('messagerequest',{'messages':messagelist_for_log,'result':msg.model_dump(),'result_followup':msg2.model_dump(),'result_unfold':msg3.model_dump()})


				function_call = {
					'function': called_func['func'],
					'arguments': {'args':args,'resolve':funccall3.function.name}
				}
			else:
				save_debug_file('messagerequest',{'messages':messagelist_for_log,'result':msg.model_dump(),'result_followup':msg2.model_dump()})
				function_call = {
					'function': called_func['func'],
					'arguments': args
				}

		else:
			function_call = None

		save_debug_file('messagerequest', {'messages': messagelist_for_log, 'result': msg.model_dump()})

		return {
			'text_content': text_content,
			'function_call': function_call,
			'cost': total_cost
		}
