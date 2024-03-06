import abc
import copy
import enum
import json
import math
import types

from typing import Dict, Any

import anthropic
import openai

from .. import config, errors, prompts
from ..helper import save_debug_file, now, describe_time


MAX_MESSAGES_IN_CONTEXT = config['ai_prompting_config']['max_context']
MAX_MESSAGE_LENGTH = 100
MAX_MESSAGES_VISION = 5
MAX_MESSAGES_IN_CONTEXT_WITH_VISION = 10
ALL_MESSAGES_IN_CONTEXT = True


class Capability(enum.Enum):
	ImageGeneration = enum.auto()
	ChatResponse = enum.auto()
	ResponderPick = enum.auto()
	CharacterCreation = enum.auto()



class Format(enum.Enum):
	Square = enum.auto()
	Landscape = enum.auto()
	Portrait = enum.auto()


def singleton(cls):
	return cls()


class AIProvider:
	options = {
		cap: []
		for name,cap in Capability._member_map_.items()
	}


	def __init_subclass__(cls,**kwargs):
		pass


	def __init__(self):
		self.config = config.get('service_config',{}).get(self.identifier,{})
		basecls = self.__class__.__base__
		for cap in self.capabilities:
			basecls.options[cap].append(self)
			#basecls.options.setdefault(cap,{})[self.identifier] = self



	@classmethod
	def __getitem__(cls,attr):
		return cls.options[attr]

	def create_image(self, keyword_prompt: list, keyword_prompt_negative: list, fulltext_prompt: str, imageformat: Format):
		raise NotImplemented()

	def respond_chat(self, chat, messagelist, allow_functioncall=True):
		raise NotImplemented()

	def get_messages(self, chat, partner, upto=None, images=False):
		raise NotImplemented()

	# TODO make subclasses for capabilities


class OpenAILike(AIProvider):

	# define for subclasses
	MODELS = []
	providerlib: types.ModuleType
	system_messages: bool = True # false implies a system parameter to the completion func
	user_names: bool = True
	alternating_messages: bool = False # this also mean no name attribute for messages
	useful_for_complex_contexts: bool = True

	client: openai.Client | anthropic.Client = None

	def init_client(self):
		if not self.client:
			self.client = self.providerlib.Client(
				api_key=self.config['apikey']
			)

	def get_create_root(self):
		return self.client.chat.completions

	def get_message_from_completion(self, completion):
		return completion.choices[0].message

	def message_to_text_content(self, message):
		return message.content

	def get_global_system_prompt(self, chat, partner):

		from ..classes import Chat, GroupChat

		prompt = "\n\n".join([
			partner.get_prompt(),
			prompts.USER_INFO_PROMPT.format(desc=config['user']['description']),
			prompts.CHAT_STYLE_PROMPT,
			(prompts.GROUPCHAT_STYLE_PROMPT if len(chat.ai_participants()) > 1 else ""),
			partner.introduction_context if partner.introduction_context else "",
			chat.get_group_desc_prompt(partner) if isinstance(chat, GroupChat) else ""
		])
		return prompt

	def is_vision_capable(self):
		if 'model_vision' in self.config:
			model = [m for m in self.MODELS if m.identifier == self.config['model_vision']][0]
		else:
			model = [m for m in self.MODELS if m.identifier == self.config['model']][0]
		return model.vision_capable

	def get_messages(self, chat, partner, upto=None, images=False):


		from ..classes import Chat, GroupChat

		if ALL_MESSAGES_IN_CONTEXT and self.useful_for_complex_contexts:
			messages = partner.get_all_accessible_messages(stop_before=upto)[-MAX_MESSAGES_IN_CONTEXT:]
		else:
			messages = chat.get_messages(stop_before=upto, visible_to=partner)[-MAX_MESSAGES_IN_CONTEXT:]

		timenow = upto.timestamp if upto else now()

		if self.system_messages:
			# CHARACTER
			yield {
				'role': "system",
				'content': "\n\n".join([
					partner.get_prompt(),
					(partner.get_knowledge_bit_prompt(long_term=True, time=timenow) or ""),
					prompts.USER_INFO_PROMPT.format(desc=config['user']['description']),
					(partner.get_knowledge_bit_prompt(long_term=False, time=timenow) or "")
				])
			}

			# STYLE
			yield {
				'role': "system",
				'content': "\n\n".join([
					prompts.CHAT_STYLE_PROMPT,
					(prompts.GROUPCHAT_STYLE_PROMPT if len(chat.ai_participants()) > 1 else "")
				])
			}

			if len(messages) < 30 and partner.introduction_context:
				yield {
					'role': "system",
					'content': "Context for the new chat: " + partner.introduction_context
				}

			if isinstance(chat, GroupChat):
				yield {
					'role': "system",
					'content': "\n\n".join([
						chat.get_group_desc_prompt(partner)
					])
				}


		# MESSAGES
		# chat before joining is not visible
		#index = next((i for i, msg in enumerate(messages) if msg.message_type == MessageType.MetaJoin and msg.author == partner), None)
		#if index is not None:
		#	messages = messages[index:]
		#	yield {
		#	    'role': "system",
		#	    'content': "[Previous chat history not visible]"
		#	}


		lasttimestamp = math.inf
		lastchat: Chat = chat
		messagebuffer = []
		currently_user = True

		# use this chat as first last chat so the context switch is announced after giving meta info about this chat
		for msg in messages:
			if self.system_messages:
				if (msg.timestamp - lasttimestamp) > (config['ai_prompting_config']['message_gap_info_min_hours']*3600):
					yield {
						'role': "system",
						'content': "{hours} hours pass... It's now {now}".format(hours=(timenow - lasttimestamp)//3600, now=describe_time(msg.timestamp))
					}

				if ALL_MESSAGES_IN_CONTEXT and lastchat and lastchat != msg.chat:
					yield {
						'role': "system",
						'content': f"--- CONTEXT SWITCH: {('Group Chat ' + msg.chat.name) if isinstance(msg.chat, GroupChat) else 'Private Chat'} ---"
					}

			lasttimestamp = msg.timestamp
			lastchat = msg.chat

			if self.alternating_messages:
				next_is_user = (msg.get_author() != partner)
				if next_is_user == currently_user:
					messagebuffer.append(msg)
				else:
					yield {
						'role': "user" if currently_user else "assistant",
						'content': "\n".join(msg.display_for_model(vision=images, add_author=True) for msg in messagebuffer) or "---"
					}
					messagebuffer.clear()
					currently_user = next_is_user

			else:
				yield {
					'role': "user" if (msg.get_author() != partner) else "assistant",
					'content': msg.display_for_model(vision=images),
					'name': msg.get_author().sanitized_handle()
				}
			if messagebuffer:
				yield {
					'role': "user" if currently_user else "assistant",
					'content': "\n".join(msg.display_for_model(vision=images, add_author=True) for msg in messagebuffer) or "---"
				}

		if self.system_messages:
			if (timenow - lasttimestamp) > (config['ai_prompting_config']['message_gap_info_min_hours']*3600):
				yield {
					'role': "system",
					'content': "{hours} hours pass... It's now {now}".format(hours=(timenow - lasttimestamp)//3600,now=describe_time(timenow))
				}
			elif (len(messages) > 0) and (messages[-1].author == partner):
				yield {
					'role': "system",
					'content': "[Continue]"
				}

			if ALL_MESSAGES_IN_CONTEXT and lastchat and lastchat != chat:
				yield {
					'role': "system",
					'content': f"--- CONTEXT SWITCH: {('Group Chat ' + chat.name) if isinstance(chat, GroupChat) else 'Private Chat'}---"
				}

			# REMINDERS
			yield {
				'role': "system",
				'content': "\n\n".join([
					prompts.GROUPCHAT_STYLE_REMINDER.format(assistant=partner) if (len(chat.ai_participants()) > 1) else "",
					prompts.CHAT_STYLE_REMINDER
				])
			}

	def respond_chat(self, chat, messagelist, responder, allow_functioncall=True):

		self.init_client()

		if any(isinstance(m['content'], list) for m in messagelist):
			model = [m for m in self.MODELS if m.identifier == self.config['model_vision']][0]
			print('use vision model!')
			extraargs = {'max_tokens': 500}
			messagelist_for_log = []
			for m in messagelist:
				logm = copy.deepcopy(m)
				try:
					logm['content'][0]['image_url']['url'] = logm['content'][0]['image_url']['url'][:30] + "...(shortened)"
				except:
					pass
				messagelist_for_log.append(logm)

		else:
			model = [m for m in self.MODELS if m.identifier == self.config['model']][0]
			messagelist_for_log = [m for m in messagelist]
			extraargs = {}

		if model.functions:
			extraargs.update({
				'tools': [{'type': 'function', 'function': f['lazyschema']} for f in chat.get_ai_accessible_funcs().values()],
				'tool_choice': ('auto' if allow_functioncall else 'none')
			})

		if not self.system_messages:
			extraargs['system'] = self.get_global_system_prompt(chat=chat, partner=responder)

		save_debug_file('messagerequest',{'messages': messagelist_for_log})

		# INITIAL COMPLETION
		try:
			completion = self.get_create_root().create(
				model=model.identifier,
				messages=messagelist,
				max_tokens=1000,
				**extraargs
			)
		except self.providerlib.BadRequestError as e:
			if 'content_policy_violation' in e.message:
				raise errors.ContentPolicyError
			else:
				raise

		total_cost = 0

		msg = self.get_message_from_completion(completion)
		cost = completion.usage
		total_cost += model.cost_input * (cost.prompt_tokens if hasattr(cost, 'prompt_tokens') else cost.input_tokens)
		total_cost += model.cost_output * (cost.completion_tokens if hasattr(cost, 'completion_tokens') else cost.output_tokens)

		text_content = msg.content
		text_content = self.message_to_text_content(msg)

		if model.functions and msg.toolcalls:
			toolcalls = msg.toolcalls
			funccall = toolcalls[0]

			# COMPLETION 2 - FULL SIGNATURE OF CALLED FUNCTION
			called_func = chat.get_ai_accessible_funcs()[funccall.function.name]
			completion = self.client.chat.completions.create(
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

				# COMPLETION 3 - EXPAND LAZY FUNCTION
				actual_functions = called_func['func'](self=chat)
				completion = self.client.chat.completions.create(
					model=model.identifier,
					messages=messagelist,
					tools=[{'type': 'function', 'function': f['schema']} for f in actual_functions.values()]
				)
				msg3 = completion.choices[0].message
				cost = completion.usage

				total_cost += model.cost_input * cost.prompt_tokens
				total_cost += model.cost_output * cost.completion_tokens

				if msg3.tool_calls:
					funccall3 = msg3.tool_calls[0]
					args = json.loads(funccall3.function.arguments)

					save_debug_file('messagerequest',{'messages':messagelist_for_log,'result':msg.model_dump(),'result_followup':msg2.model_dump(),'result_unfold':msg3.model_dump()})

					function_call = {
						'function': called_func['func'],
						'arguments': {'args':args,'resolve':funccall3.function.name}
					}
				else:
					function_call = None

			elif called_func['nonterminating']:

				tool_id = funccall2.id

				extramsgs = [msg2.model_dump()] + [{'role':'tool','tool_call_id':tool_id,'content':"Success!"}]
				messagelist += extramsgs
				messagelist_for_log += extramsgs

				del extramsgs[0]['function_call'] # weird design but ok

				# COMPLETION 3 - COMPLETE AFTER CALLING FUNC
				completion = self.client.chat.completions.create(
					model=model.identifier,
					messages=messagelist,
					tools=[{'type': 'function', 'function': called_func['schema']}],
					tool_choice='none'
				)
				msg3 = completion.choices[0].message
				cost = completion.usage

				total_cost += model.cost_input * cost.prompt_tokens
				total_cost += model.cost_output * cost.completion_tokens

				function_call = {
					'function': called_func['func'],
					'arguments': args
				}
				text_content = msg3.content

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


from . import anydream, open_ai, getimg, anthropicai

AI: Dict[str, AIProvider] = {
	name: [provider for provider in AIProvider.options[cap] if provider.identifier == config['use_service'][name]][0]
	for name, cap in Capability._member_map_.items()
}
