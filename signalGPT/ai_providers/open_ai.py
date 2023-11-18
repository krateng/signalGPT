import json

from . import AIProvider, Capability, singleton
import openai

from ..helper import save_debug_file


@singleton
class OpenAI(AIProvider):
	capabilities = [
		Capability.ImageGeneration,
		Capability.ChatResponse
	]
	identifier = 'openai'

	def create_image(self, keyword_prompt, keyword_prompt_negative, fulltext_prompt, imageformat):

		result = openai.Image.create(
			prompt=fulltext_prompt,
			n=1,
			size="1024x1024"
		)

		img = result['data'][0]['url']

		return img

	def respond_chat(self, chat, messagelist, ai_prov_config={}, allow_functioncall=True):

		funcargs = {
			'tools':[{'type':'function','function':f['lazyschema']} for f in chat.get_ai_accessible_funcs().values()],
			'tool_choice':('auto' if allow_functioncall else 'none')
		} if ai_prov_config['model'].functions else {}

		completion = openai.chat.completions.create(
			model=ai_prov_config['model'].identifier,
			messages=messagelist,
			**funcargs
		)

		total_cost = 0

		msg = completion.choices[0].message
		cost = completion.usage
		total_cost += ai_prov_config['model'].cost_input * cost.prompt_tokens
		total_cost += ai_prov_config['model'].cost_output * cost.completion_tokens

		text_content = msg.content
		toolcalls = msg.tool_calls

		if toolcalls:
			funccall = toolcalls[0]

			# ai indicated it wants to use that function, so we now provide it with the full signature
			called_func = chat.get_ai_accessible_funcs()[funccall.function.name]
			completion = openai.chat.completions.create(
				model=ai_prov_config['model'].identifier,
				messages=messagelist,
				tools=[{'type': 'function', 'function': called_func['schema']}],
				tool_choice={'type': 'function', 'function': {'name': funccall.function.name}}
			)
			msg2 = completion.choices[0].message
			cost = completion.usage
			total_cost += ai_prov_config['model'].cost_input * cost.prompt_tokens
			total_cost += ai_prov_config['model'].cost_output * cost.completion_tokens

			funccall2 = msg2.tool_calls[0]
			args = json.loads(funccall2.function.arguments)

			if called_func['lazy']:
				actual_functions = called_func['func'](self=chat)
				# this is a func that has no args yet to save tokens
				# once the AI decides to call it, we ask it again, this time with details

				completion = openai.chat.completions.create(
					model=ai_prov_config['model'].identifier,
					messages=messagelist,
					tools=[{'type': 'function', 'function': f['schema']} for f in actual_functions.values()]
				)
				msg3 = completion.choices[0].message
				cost = completion.usage

				total_cost += ai_prov_config['model'].cost_input * cost.prompt_tokens
				total_cost += ai_prov_config['model'].cost_output * cost.completion_tokens

				funccall3 = msg3.tool_calls[0]
				args = json.loads(funccall3.function.arguments)

				save_debug_file('messagerequest',{'messages':messagelist,'result':msg.model_dump(),'result_followup':msg2.model_dump(),'result_unfold':msg3.model_dump()})


				function_call = {
					'function': called_func['func'],
					'arguments': {'args':args,'resolve':funccall3.function.name}
				}
			else:
				save_debug_file('messagerequest',{'messages':messagelist,'result':msg.model_dump(),'result_followup':msg2.model_dump()})
				function_call = {
					'function': called_func['func'],
					'arguments': args
				}

		else:
			function_call = None

		save_debug_file('messagerequest', {'messages': messagelist, 'result': msg.model_dump()})

		return {
			'text_content': text_content,
			'function_call': function_call,
			'cost': total_cost
		}
