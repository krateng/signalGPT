import json
import base64
import mimetypes
import os
import random
import time
from datetime import datetime, timezone, timedelta
import emoji
import enum
import math

from pprint import pprint


from sqlalchemy import create_engine, Table, Column, Integer, String, Boolean, Enum, ForeignKey, and_
from sqlalchemy.types import TypeDecorator, Text
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from sqlalchemy.ext.declarative import declarative_base


from .__init__ import config
from .metaprompt import create_character_info, create_character_image, guess_next_responder, summarize_chat
from .helper import save_debug_file
from . import memes, prompts
from .ai_providers import AI, Format, Capability

MAX_MESSAGES_IN_CONTEXT = config['ai_prompting_config']['max_context']
MAX_MESSAGE_LENGTH = 100
MAX_MESSAGES_VISION = 5
MAX_MESSAGES_IN_CONTEXT_WITH_VISION = 10





def now():
	return int(datetime.now(timezone.utc).timestamp())

def describe_time(timestamp):
	time = datetime.fromtimestamp(timestamp,tz=timezone.utc)
	offset = timedelta(hours=config['user']['utc_offset'])
	local_time = time + offset
	return local_time.strftime('%A %B %d, %H:%M')

def generate_uid():
	uid = ""
	for i in range(32):
		if i % 4 == 0 and i != 0:
			uid += "-"
		uid += random.choice("0123456789abcdef")
	return uid

def generate_color():
	hex = "#"
	for i in range(6):
		hex += random.choice("0123456789abcdef")
	return hex

def bold(txt):
	return "\033[1m" + txt + "\033[0m"

def get_media_type(filename):
	if filename:
		ext = filename.split('.')[-1].lower()
		if ext in ['mp4','mkv','webm','avi']: return 'Video'
		if ext in ['jpg','jpeg','png','gif','webp']: return 'Image'
		if ext in ['mp3','wav','flac']: return 'Audio'


def image_encode_b64(filename):
	mime_type, _ = mimetypes.guess_type(filename)
	if mime_type is None:
		mime_type = 'application/octet-stream'

	with open(filename, "rb") as image_file:
		encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

	return f'data:{mime_type};base64,{encoded_string}'


def ai_accessible_function(func):
	func._aiaccessible = True

	func._lazyschema = {
		'name':func.__name__,
		'description':func.__doc__,
		'parameters':{
			'type':'object',
			'properties':{}
		}
	}

	func._schema = {
		**func._lazyschema,
		'parameters':{
			'type':'object',
			'required':[param for param in func.__annotations__ if func.__annotations__[param][1]],
			'properties':{
				name: {
					'type':type[0],
					'items': {'type':type[1] },
					'description': desc
				} if len(type)>1 else {
					'type':type[0],
					'description': desc
				}
				for name,(type,req,desc) in func.__annotations__.items()
			}
		}
	}

	return func

def lazy(func):
	func._lazy = True
	return func




Base = declarative_base()


# CUSTOM COLUMN TYPE
class JsonDict(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value

# ASSOCIATIONS
chat_to_member = Table('chat_members',Base.metadata,
	Column("chat_id",Integer,ForeignKey('chats.uid')),
	Column("person_handle",String,ForeignKey('people.handle'))
)



class Partner(Base):
	__tablename__ = 'people'
	uid = Column(Integer)
	handle = Column(String,primary_key=True)
	name = Column(String)
	male = Column(Boolean,default=False)
	bio = Column(String)
	image = Column(String)
	instructions = Column(String)
	introduction_context = Column(String)
	prompts = Column(JsonDict)
	#linguistic_signature = Column(String) # comma separated
	user_defined = Column(Boolean)
	friend = Column(Boolean,default=False)
	color = Column(String,nullable=True)

	chats = relationship("GroupChat",secondary=chat_to_member,back_populates="members")
	direct_chat = relationship('DirectChat',back_populates='partner',uselist=False)

	def __init__(self,**data):

		if "from_desc" in data:
			results = create_character_info(data.pop('from_desc'))
			data['name'] = results['name']
			data['handle'] = results['handle']
			data['bio'] = results['bio']
			data['instructions'] = results['prompt']
			data['male'] = results['male']

			data['image'] = create_character_image(results['img_prompt_keywords'],male=data['male'])

		super().__init__(**data)

		self.color = self.color or generate_color()
		#self.uid = self.uid or generate_uid()



	def start_direct_chat(self,session):
		if self.direct_chat:
			return self.direct_chat

		direct_chat = DirectChat()
		direct_chat.partner = self
		session.add(direct_chat)
		session.commit()
		return direct_chat

	def serialize(self):
		return {
			'name':self.name,
			'handle':self.handle,
			'bio':self.bio,
			#'uid':self.uid,
			'image':self.image,
			'instructions':self.instructions,
			'friend':self.friend,
			'direct_chat': {'ref':'chats','key':self.direct_chat.uid} if self.direct_chat else None
			#'direct_chat':self.direct_chat.serialize() if self.direct_chat else None
		}
	def add_contact(self):
		self.permanent = True
		with open(os.path.join("partners",self.handle + ".json"),"w") as fd:
			json.dump(self.serialize(),fd,indent=4)

	def get_prompt(self):
		return prompts.CHARACTER_INSTRUCTION_PROMPT.format(assistant=self)

	def get_relevant_knowledge_bits(self,long_term):
		session = ScopedSession()
		bits = session.query(KnowledgeBit).where(and_(KnowledgeBit.author == self,KnowledgeBit.long_term == long_term)).all() #for now only owned ones
		return bits

	def get_knowledge_bit_prompt(self,long_term):
		if self.get_relevant_knowledge_bits(long_term):
			if long_term:
				result = "ADDITIONAL INFO:"
			else:
				result = "CURRENT SITUATION:"
			for bit in self.get_relevant_knowledge_bits(long_term):
				result += f"\n* [fact:{bit.number}] {bit.desc}"
			#result += "\nOnly update or remove these knowledge bits when things have significantly changed"
			return result
		else:
			return None

class Protagonist:
	name = config['user']['name']
	color = "blue"
	uid = 0
	handle = config['user']['handle']


class MessageType(enum.Enum):
	Text = 1
	Image = 2
	Video = 3
	Audio = 4
	Contact = 8
	MetaJoin = 10
	MetaLeave = 11
	MetaRename = 20
	MetaChangePicture = 21


class Message(Base):
	__tablename__ = 'messages'

	uid = Column(Integer,primary_key=True)
	chat_id = Column(Integer,ForeignKey('chats.uid'))
	chat = relationship('Chat',backref='messages')
	author_handle = Column(String,ForeignKey('people.handle'))
	author = relationship('Partner',backref='messages',foreign_keys=[author_handle])
	timestamp = Column(Integer)
	message_type = Column(Enum(MessageType),default=MessageType.Text)
	content = Column(String,default="")
	content_secondary = Column(String) # used for media description
	media_attached = Column(String)
	linked_contact_handle = Column(String,ForeignKey('people.handle'))
	linked_contact = relationship('Partner',foreign_keys=[linked_contact_handle])

	def __init__(self,**data):
		if 'content' in data:
			data['content'] = data['content'].strip()

		super().__init__(**data)

	def get_author(self):
		return self.author or Protagonist

	def is_from_user(self):
		return self.author_handle is None

	def print(self):
		self.get_author().print_message(self.content)


	def serialize(self):
		return {
			'uid': self.uid,
			#'author':self.get_author().handle,
			'author': {'ref':'contacts','key':self.get_author().handle} if not self.is_from_user() else None,
			'own':(self.get_author() is Protagonist),
			'chat': {'ref':'chats','key':self.chat.uid},
			'content':self.content or "",
			'linked_entity': {'ref': 'contacts','key':self.linked_contact.handle } if self.message_type == MessageType.Contact else None,
			'message_type':self.message_type.name if self.message_type else None,
			#'media_attached':self.media_attached,
			#'media_type':get_media_type(self.media_attached),
			'timestamp':self.timestamp,
			'display_simplified': self.content and (len(self.content)<6) and ("" == emoji.replace_emoji(self.content,replace=''))
		}

	def display_for_model(self,vision=False,add_author=None):

		prefix = f"{add_author.name}: " if add_author else ""

		if self.message_type in [None,MessageType.Text]:
			return prefix + self.content
		elif (self.message_type == MessageType.Image) and vision:
			if self.content.startswith("data:"):
				encodedimg = self.content
			else:
				encodedimg = image_encode_b64('.' + self.content)
			msg = [
				{
					'type':'image_url',
					'image_url':{
						'url': encodedimg
					}
				}
			]
			if add_author:
				msg += [
					{
						'type':'text',
						'text': f"Sent by {add_author.name}"
					}
				]
			return msg
		elif self.message_type in [MessageType.Image, MessageType.Video, MessageType.Audio]:
			return prefix + f"[{self.message_type.name} attached: {self.content_secondary or ''}]"
		elif self.message_type == MessageType.Contact:
			return prefix + f"[Contact attached: @{self.linked_contact.handle}]"
		elif self.message_type == MessageType.MetaJoin:
			return prefix + "[has been added to chat]"
		elif self.message_type == MessageType.MetaLeave:
			return prefix + "[has left the chat]"
		elif self.message_type == MessageType.MetaRename:
			return prefix + f"[has renamed the chat to '{self.content}']"
		elif self.message_type == MessageType.MetaChangePicture:
			return prefix + f"[has changed the group picture: {self.content_secondary or ''}]"
		else:
			print("WEIRD MESSAGE:",self.message_type)
			return ""


class ChatSummary(Base):
	__tablename__ = "chatsummaries"

	uid = Column(Integer,primary_key=True)
	chat_uid = Column(String,ForeignKey('chats.uid'))
	chat = relationship('Chat',backref='summaries')


class Chat(Base):
	__tablename__ = 'chats'

	uid = Column(Integer,primary_key=True)
	subtype = Column(String)
	total_paid = Column(Integer,default=0)
	# 10 000 = 1 ct
	# 1 000 000 = 1 usd
	__mapper_args__ = {'polymorphic_on': subtype}

	def get_ai_accessible_funcs(self):
		cls = self.__class__
		fulldict = {}
		for baseclass in reversed(cls.__mro__):
			fulldict.update(baseclass.__dict__)

		funcs = [f for f in fulldict.values() if getattr(f,'_aiaccessible',False)]
		funcs = {f.__name__:{'schema':f._schema,'lazyschema':f._lazyschema,'func':f,'lazy':getattr(f,'_lazy',False)} for f in funcs}
		return funcs


	@ai_accessible_function
	def send_image(self,author,timestamp,
		prompt: (('array','string'),True,"Keywords that objectively describe what the image shows to someone who has no context or knowledge of you or this chat.\
			If the picture includes yourself or other chat participants, make sure the keywords describe your or their appearance to the best of your knowledge. \
			Don't just add your name, add things like your ethnicity, hair color etc.\
			You may use quite a few keywords here and go into detail.") = [],
		prompt_fulltext: (('string',),True,"The prompt for the image, but as a continuous descriptive text.") = "" ,
		negative_prompt: (('array','string'),False,"Keywords for undesirable traits or content of the picture.") = [],
		selfie: (('boolean',),True,"Whether this is a picture of yourself.")=False,
		short_desc: (('string',),True,"A short description of what the picture shows for visually impaired users.") = "",
		landscape: (('boolean',),False,"Whether to send a picture in landscape mode instead of portrait mode") = False
	):
		"Send an image in the chat. It should be used very rarely, only when sending a picture fits the context or is requested.\
		You also cannot randomly send pictures of other people, unless context indicates that you're currently in the same loction together.\
		Do not simply send a picture just because the previous message is a picture."
		imageformat = Format.Landscape if landscape else Format.Portrait

		img = AI['ImageGeneration'].create_image(keyword_prompt=prompt, keyword_prompt_negative=negative_prompt, fulltext_prompt=prompt_fulltext, imageformat=imageformat)
		m = self.add_message(author=author,message_type=MessageType.Image,content=img,content_secondary=short_desc)
		yield m

	@ai_accessible_function
	def send_contact(self,author,timestamp,
		name: (('string',),True,"The contact's informal name - prename or nickname"),
		male: (('boolean',),True,"True if the contact is male, false if they are female."),
		short_description: (('string',),True,"Objectively describe the contact. Include name and sex again, but also character, ethnicity, looks, etc. without any relation to the current chat context.\
		Please do not editorialize this according to your character, but write neutrally."),
		context_introduction: (('string',),True,"A summary directed at the new contact (in second person), detailing all interactions and relevant events involving them up to this point (even their own actions and opinions), speaking as a neutral instructor (not yourself)."),
		add_to_groupchat: (('boolean',),False,"Whether to add this contact to the chat instead of simply sending them. Only works in group chats.") = False
	):
		"Send contact info of a person you know to the chat. It should only be used when a chat partner explicitly requests their contact details, not simply everytime someone mentions another person."

		session = ScopedSession()

		char = session.query(Partner).where(Partner.name==name).first()
		if not char:
			char = Partner(from_desc=short_description,introduction_context=context_introduction)
			session.add(char)
			session.commit()
		handle = char.handle

		if add_to_groupchat and isinstance(self,GroupChat):
			m = self.add_person(char)
			yield m
		else:
			m = self.add_message(author=author,message_type=MessageType.Contact,linked_contact=char)
			yield m


	@ai_accessible_function
	@lazy
	def send_meme(self,author,timestamp,resolve=None,args={}):
		"Send a meme"

		customfuncs = memes.get_functions()
		if resolve:
			func = customfuncs[resolve]['func']
			result = func(**args)
			m = self.add_message(author=author,message_type=MessageType.Image,content=result['image'],content_secondary=result['desc'])
			return [m]
		else:
			return customfuncs

	@ai_accessible_function
	def update_knowledge_bit(self,author,timestamp,
		short_desc: (('string',),True,"A short description of the knowledge, e.g. 'Closer relationship' or 'Vacation plans'"),
		full_desc: (('string',),True,"A concise, objective, third-person summary of the new knowledge, e.g. 'John has invited Amy, Bob and Carol to a vacation in Switzerland. They are currently planning it.'"),
		#important: (('boolean',),True,"Whether the information is so vital for you that it should always be in your context window. This should be true for significant changes in your character, situation or relationship that affect your base prompt."),
		long_term: (('boolean',),True,"Whether this is long term information (like your character or relationship having changed) or some temporary info (like what's currently happening)"),
		number: (('integer',),False,"Only needed when updating an existing knowledge bit.") = None
	):
		"""Create or edit a knowledge bit. Use this function when you learn about relevant details concerning your character or relationships, AND when learning details about what you are currently doing.
		Don't constantly create new bits about things that are already in your knowledge bits.
		ALWAYS write a normal response first before using this function.
		You should use knowledge bits to keep track of:
		- changes to your character or a relationship (when the recent chat indicates that your original prompt is no longer accurate)
		- things that you learn in the chat that are relevant and should be permanently saved, but are not in your prompt yet
		- current events that you learned about and that are relevant for your future conversations (e.g. that you currently are in a specific location)
		Make sure to delete knowledge bits after they are no longer relevant, especially about short term events.
		Permanent changes to your character or relationship should not be deleted.
		"""

		session = ScopedSession()

		print('add knowledge',short_desc)
		kb = KnowledgeBit(shortdesc=short_desc,desc=full_desc,author=author,long_term=long_term,timestamp=timestamp,number=number)
		session.add(kb)
		session.commit()

		return []

	def readable_cost(self):
		cents = self.total_paid // 10000
		dollars = cents // 100
		remainder = cents % 100
		return f"USD {dollars}.{remainder:02}"

	def serialize(self):
		return {
			**self.serialize_short(),
			'messages':[msg.serialize() for msg in self.get_messages()],
			'cost':self.readable_cost()
		}

	def add_message(self,author=None,timestamp=None,**keys):
		if msgt := keys.pop('msgtype',None):
			keys['message_type'] = {
				'image':MessageType.Image,
				'video':MessageType.Video
			}[msgt]
		m = Message(**keys)
		m.chat = self
		if author is Protagonist:
			m.author = None
		else:
			m.author = author
		m.timestamp = timestamp or now()
		return m

	def get_messages_upto(self,upto):
		if upto:
			relevant_messages = []
			for msg in self.messages:
				if msg is upto:
					break
				else:
					relevant_messages.append(msg)
			return relevant_messages
		else:
			return self.messages

	def get_messages(self,stop_before=None):
		msgs = sorted(self.messages,key=lambda x:x.timestamp)
		if stop_before:
			relevant_messages = []
			for msg in msgs:
				if (msg is stop_before) or (isinstance(stop_before,int) and (msg.timestamp >= stop_before)):
					break
				else:
					relevant_messages.append(msg)
			return relevant_messages
		else:
			return msgs

	def send_message(self,content=None,msgtype=None):
		return self.add_message(Protagonist,content=content,msgtype=msgtype)

	def get_response(self,replace=None,responder=None):
		if not responder:
			responder = replace.author if replace else self.pick_next_responder()

		vision_capable = AI['ChatResponse'].is_vision_capable()
		use_vision = vision_capable and any(m.message_type == MessageType.Image for m in self.get_messages()[-MAX_MESSAGES_VISION:])

		messages = self.get_openai_msg_list(from_perspective=responder,upto=replace,images=use_vision)
		if use_vision:
			messages = messages[-MAX_MESSAGES_IN_CONTEXT_WITH_VISION:]

		result = AI['ChatResponse'].respond_chat(chat=self, messagelist=messages, allow_functioncall=(not replace))

		self.total_paid += result['cost']

		# TEXT CONTENT
		if content := result['text_content']:
			content = self.clean_content(content,responder)

			if replace:
				replace.content = content
				replace.message_type = MessageType.Text
				yield replace
			else:
				for contpart in [contentpart for contentpart in content.split("\n\n") if contentpart]:
					m = self.add_message(author=responder,content=contpart)
					yield m
					time.sleep(1)

		# FUNCTIONS
		if funccall := result['function_call']:
			yield from funccall['function'](self=self,author=responder,timestamp=replace.timestamp if replace else m.timestamp,**funccall['arguments'])

	def get_summary(self,partner,external=False,timestamp=None):

		messages = self.get_messages(stop_before=timestamp)
		result = summarize_chat(messages,perspective=partner,external=external)

		return result


class DirectChat(Chat):
	__tablename__ = 'directchats'
	uid = Column(Integer,ForeignKey('chats.uid'),primary_key=True)

	partner_handle = Column(String,ForeignKey('people.handle'))
	partner = relationship('Partner',back_populates='direct_chat',uselist=False)

	__mapper_args__ = {'polymorphic_identity': 'direct'}

	def serialize_short(self):
		return {
			'uid':self.uid,
			#'partner':self.partner.serialize(),
			'partner': {'ref':'contacts','key':self.partner.handle},
			#'partner':self.partner_handle,
			#'name':self.partner.name,
			'groupchat':False,
			#'desc':self.partner.bio,
			#'image':self.partner.image,
			'latest_message':self.get_messages()[-1].serialize() if self.messages else None
		}

	def get_openai_messages(self,upto=None,images=False):
		messages = self.get_messages(stop_before=upto)[-MAX_MESSAGES_IN_CONTEXT:]

		timenow = upto.timestamp if upto else now()

		# CHARACTER
		yield {
			'role':"system",
			'content': "\n\n".join([
				self.partner.get_prompt(),
				self.partner.get_knowledge_bit_prompt(long_term=True) or "",
				prompts.USER_INFO_PROMPT.format(desc=config['user']['description'])
			])
		}

		# STYLE
		yield {
			'role':"system",
			'content': "\n\n".join([
				prompts.CHAT_STYLE_PROMPT
			])
		}

		# CHAT
		if len(messages) < 50 and self.partner.introduction_context:
			yield {
				'role': "system",
				'content': "Context for the new chat: " + self.partner.introduction_context
			}

		# MESSAGES
		lasttimestamp = math.inf
		for msg in messages:
			if (msg.timestamp - lasttimestamp) > (config['ai_prompting_config']['message_gap_info_min_hours']*3600):
				yield {
					'role':"system",
					'content':"{hours} hours pass... {now}".format(hours=(timenow - lasttimestamp)//3600,now=describe_time(msg.timestamp))
				}
			lasttimestamp = msg.timestamp

			yield {
				'role':"user" if (msg.is_from_user()) else "assistant",
				'content': msg.display_for_model(vision=images)
			}

		if (timenow - lasttimestamp) > (config['ai_prompting_config']['message_gap_info_min_hours']*3600):
			yield {
				'role':"system",
				'content':"{hours} hours pass... {now}".format(hours=(timenow - lasttimestamp)//3600,now=describe_time(timenow))
			}
		elif (len(messages)>0) and (not messages[-1].is_from_user()):
			yield {
				'role':"system",
				'content': "[Continue]"
			}

		# REMINDERS
		yield {
			'role': "system",
			'content': "\n\n".join([
				prompts.CHAT_STYLE_REMINDER,
				(self.partner.get_knowledge_bit_prompt(long_term=False) or "")
			])
		}

	def get_openai_msg_list(self,upto=None,from_perspective=None,images=False):
		result = list(self.get_openai_messages(upto=upto,images=images))
		#from pprint import pprint
		#pprint(result)
		return result

	def clean_content(self,content,responder):
		return content

	def pick_next_responder(self):
		return self.partner


class GroupChat(Chat):
	__tablename__ = 'groupchats'
	uid = Column(Integer,ForeignKey('chats.uid'),primary_key=True)

	name = Column(String,default="New Group")
	desc = Column(String,default="")
	image = Column(String)

	members = relationship("Partner",secondary=chat_to_member,back_populates="chats")

	__mapper_args__ = {'polymorphic_identity': 'group'}

	def get_group_desc_prompt(self,perspective):
		memberlist = ', '.join(
			f"{p.name} (@{p.handle})"
			for p in self.members + [Protagonist] if p is not perspective
		)

		return f"Group Chat Name: {self.name}\nGroup Chat Members: You, {memberlist}"

	@ai_accessible_function
	def rename_chat(self,author,timestamp,
		name: (('string',),True,"New name")
	):
		"Can be used to rename the current group chat. This should be used only when there is a specific reason, or sometimes for comedic effect."

		self.name = name
		m = self.add_message(message_type=MessageType.MetaRename,author=author,content=name)
		yield m

	@ai_accessible_function
	def change_group_picture(self,author,timestamp,
		prompt: (('array','string'),True,"Keywords that describe the image"),
		prompt_fulltext: (('string',),True,"Full text description of the image"),
		negative_prompt: (('array','string'),False,"Keywords for undesirable traits or content of the picture.") = []
	):
		"Can be used to change the group picture. This should only be used when there is a specific reason, or rarely for comedic effect."

		img = AI['ImageGeneration'].create_image(keyword_prompt=prompt, keyword_prompt_negative=negative_prompt, fulltext_prompt=prompt_fulltext, imageformat=Format.Square)
		self.image = img
		m = self.add_message(message_type=MessageType.MetaChangePicture,author=author,content=img)
		yield m

	def serialize_short(self):
		return {
			'uid':self.uid,
			'name':self.name,
			'groupchat':True,
			'desc':self.desc,
			'image':self.image,
			'partners': [{'ref':'contacts','key':p.handle} for p in self.members],
			#'partners':[p.serialize() for p in self.partners],
			#'partners':{p.handle:p.name for p in self.members},
			'latest_message':self.get_messages()[-1].serialize() if self.messages else None
		}

	def get_openai_messages(self,partner,upto=None,images=False):
		messages = self.get_messages(stop_before=upto)[-MAX_MESSAGES_IN_CONTEXT:]

		timenow = upto.timestamp if upto else now()

		# CHARACTER
		yield {
			'role':"system",
			'content': "\n\n".join([
				partner.get_prompt(),
				(partner.get_knowledge_bit_prompt(long_term=True) or ""),
				prompts.USER_INFO_PROMPT.format(desc=config['user']['description'])
			])
		}

		# STYLE
		yield {
			'role':"system",
			'content': "\n\n".join([
				prompts.CHAT_STYLE_PROMPT,
				(prompts.GROUPCHAT_STYLE_PROMPT if len(self.members) > 1 else "")
			])
		}

		# GROUP INFO
		yield {
			'role':"system",
			'content': "\n\n".join([
				self.get_group_desc_prompt(partner)
			])
		}

		# MESSAGES
		# chat before joining is not visible
		index = next((i for i, msg in enumerate(messages) if msg.message_type == MessageType.MetaJoin and msg.author == partner), None)
		if index is not None:
			messages = messages[index:]
			yield {
			    'role': "system",
			    'content': "[Previous chat history not visible]"
			}

		lasttimestamp = math.inf
		for msg in messages:
			if (msg.timestamp - lasttimestamp) > (config['ai_prompting_config']['message_gap_info_min_hours']*3600):
				yield {
					'role':"system",
					'content':"{hours} hours pass... It's now {now}".format(hours=(timenow - lasttimestamp)//3600,now=describe_time(msg.timestamp))
				}
			lasttimestamp = msg.timestamp


			yield {
				'role':"user" if (msg.get_author() != partner) else "assistant",
				'content': msg.display_for_model(vision=images),
				'name': msg.get_author().handle
			}

		if (timenow - lasttimestamp) > (config['ai_prompting_config']['message_gap_info_min_hours']*3600):
			yield {
				'role':"system",
				'content':"{hours} hours pass... It's now {now}".format(hours=(timenow - lasttimestamp)//3600,now=describe_time(timenow))
			}
		elif (len(messages)>0) and (messages[-1].author == partner):
			yield {
				'role':"system",
				'content': "[Continue]"
			}

		# REMINDERS
		yield {
			'role': "system",
			'content': "\n\n".join([
				prompts.GROUPCHAT_STYLE_REMINDER.format(assistant=partner) if (len(self.members) > 1) else "",
				prompts.CHAT_STYLE_REMINDER,
				(partner.get_knowledge_bit_prompt(long_term=False) or "")
			])
		}

	def get_openai_msg_list(self,from_perspective,upto=None,images=False):
		result = list(self.get_openai_messages(partner=from_perspective,upto=upto,images=images))
		#from pprint import pprint
		#pprint(result)

		return result

	def pick_next_responder(self):

		responder = guess_next_responder(self.get_messages(),self.members,user=Protagonist)

		if not responder:
			# Fallback
			chances = {p:100 for p in self.members}
			mentioned = set()
			for msg in self.messages[-7:]:
				for p in self.members:
					if f"@{p.handle}" in msg.content:
						# person was mentioned
						mentioned.add(p)
					elif p is msg.author:
						# person responded after mention
						mentioned.discard(p)


			for index,msg in enumerate(reversed(self.messages[-7:])):
				# last responder never responds, going further back the penalty is reduced
				if msg.author:
					chances[msg.author] *= (index / 10)
			for p in mentioned:
				chances[p] += (200 * len(chances))

			responder = random.choices(list(chances.keys()),weights=chances.values(),k=1)[0]

		return responder

	def clean_content(self,content,responder):
		unwanted_prefix = f"{responder.name}: "
		if content.startswith(unwanted_prefix):
			content = content[len(unwanted_prefix):]
		return content

	def add_person(self,person):
		if person not in self.members:
			self.members.append(person)
			m = Message(
				message_type = MessageType.MetaJoin,
				author = person,
				chat = self,
				timestamp = now()
			)
			self.messages.append(m)
			return m


class KnowledgeBit(Base):
	__tablename__ = 'knowledgebits'
	uid = Column(Integer,primary_key=True)

	number = Column(Integer)
	timestamp = Column(Integer)
	shortdesc = Column(String)
	desc = Column(String)
	important = Column(Boolean)
	long_term = Column(Boolean)
	author_handle = Column(String,ForeignKey("people.handle"))

	author = relationship("Partner",backref='knowledge')


class KnowledgeAccess(Base):
	__tablename__ = "knowledgebits_access"
	uid = Column(Integer,primary_key=True)

	bit_uid = Column(Integer,ForeignKey("knowledgebits.uid"))
	authorized_person_handle = Column(String,ForeignKey("people.handle"))


def maintenance():
	with Session() as session:

		# remove contacts with no chats and no messages sharing them
		for partner in session.query(Partner).all():
			if (not partner.chats) and (not partner.direct_chat) and (not partner.friend):
				for msg in session.query(Message).all():
					if msg.message_type == MessageType.Contact and msg.linked_contact == partner:
						print("Not deleting",partner.name,"because they are sent as a contact.")
						break
				else:
					print("Deleting",partner.name)
					session.delete(partner)
			if partner.friend:
				partner.start_direct_chat(session)
		session.commit()

		# update legacy data
		for msg in  session.query(Message).all():
			if msg.media_attached:
				if msg.content:
					print("Message",msg,"contains both content and media_attached!")
				else:
					print("DB Legacy update!")
					msg.content = msg.media_attached
					msg.media_attached = None

			if (msg.message_type == MessageType.Contact) and (not msg.linked_contact):
				partner = session.query(Partner).where(Partner.handle == msg.content).first()
				msg.linked_contact = partner
		session.commit()

		# delete unused pics
		prefix = "/media/"
		media = [ prefix + filename for filename in os.listdir("media") ]

		for obj in (session.query(Partner).all() + session.query(GroupChat).all()):
			if obj.image and (obj.image in media):
				media.remove(obj.image)
		for obj in session.query(Message).all():
			if obj.message_type in [MessageType.Image,MessageType.Video]:
				if obj.content in media:
					media.remove(obj.content)
				if obj.media_attached in media:
					media.remove(obj.media_attached)
		for filepath in media:
			realfile = 'media/' + filepath.split('/')[-1]
			print('Delete',realfile)
			os.remove(realfile)

		# make sure group titles are correct
		for groupchat in session.query(GroupChat).all():
			rename_msgs = [msg for msg in groupchat.get_messages() if msg.message_type == MessageType.MetaRename]
			if rename_msgs:
				if rename_msgs[-1].content != groupchat.name:
					print("Renaming",groupchat.name,"to",rename_msgs[-1].content)
					groupchat.name = rename_msgs[-1].content
		session.commit()


engine = create_engine('sqlite:///database.sqlite')
# ONLY TESTING
#Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
ScopedSession = scoped_session(Session)


from . import loadfiles
loadfiles.load_all()


maintenance()
