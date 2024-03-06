import json
import base64
import mimetypes
import os
import random
import time
import typing
from typing import Iterable, List

import emoji
import enum

from pprint import pprint


from sqlalchemy import create_engine, Table, Column, Integer, String, Boolean, Enum, ForeignKey, and_
from sqlalchemy.types import TypeDecorator, Text
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from sqlalchemy.ext.declarative import declarative_base


from .__init__ import config
from .metaprompt import create_character_info, create_character_image, guess_next_responder, summarize_chat
from .helper import  now, describe_time, save_debug_file
from . import memes, prompts, errors
from .ai_providers import AI, Format, AIProvider

MAX_MESSAGES_IN_CONTEXT = config['ai_prompting_config']['max_context']
MAX_MESSAGE_LENGTH = 100
MAX_MESSAGES_VISION = 5
MAX_MESSAGES_IN_CONTEXT_WITH_VISION = 10
ALL_MESSAGES_IN_CONTEXT = True







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


type_mapping = {
	int: 'integer',
	float: 'number',
	str: 'string',
	bool: 'boolean'
}


def ai_accessible_function(**argument_descriptions):
	def ai_accessible_maker(func):

		func._aiaccessible = True

		func._lazyschema = {
			'name': func.__name__,
			'description': func.__doc__,
			'parameters': {
				'type': 'object',
				'properties': {}
			}
		}

		func._schema = {
			**func._lazyschema,
			'parameters': {
				'type': 'object',
				'required': [param for param in func.__annotations__ if param not in ('author', 'timestamp')], # todo check defaults
				'properties': {}
			}
		}

		for param, annotation in typing.get_type_hints(func).items():
			if param in ('author', 'timestamp'):
				continue

			annotation_local = annotation

			if hasattr(annotation_local, '__args__') and type(None) in annotation_local.__args__:
				func._schema['parameters']['required'].remove(param)
				annotation_local = [a for a in annotation_local.__args__ if a is not type(None)][0]

			if hasattr(annotation_local, '__origin__') and annotation_local.__origin__ == list:
				func._schema['parameters']['properties'][param] = {
					'type': 'array',
					'items': {'type': type_mapping[annotation_local.__args__[0]] },
					'description': argument_descriptions[param]
				}
			else:
				func._schema['parameters']['properties'][param] = {
					'type': type_mapping[annotation_local],
					'description': argument_descriptions[param]
				}

		return func

	return ai_accessible_maker


def lazy(func):
	func._lazy = True
	return func


def non_terminating(func):
	func._nonterminating = True
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
chat_to_member = Table('chat_members', Base.metadata,
	Column("chat_id", Integer, ForeignKey('chats.uid')),
	Column("person_handle", String, ForeignKey('people.handle'))
)


class Partner(Base):
	__tablename__ = 'people'
	uid = Column(Integer)
	handle = Column(String, primary_key=True)
	name = Column(String)
	male = Column(Boolean, default=False)
	bio = Column(String)
	image = Column(String)
	instructions = Column(String)
	introduction_context = Column(String)
	prompts = Column(JsonDict)
	#linguistic_signature = Column(String) # comma separated
	user_defined = Column(Boolean)
	friend = Column(Boolean, default=False)
	pinned = Column(Boolean, default=False)
	color = Column(String, nullable=True)

	chats = relationship("GroupChat",secondary=chat_to_member,back_populates="members")
	direct_chat = relationship('DirectChat',back_populates='partner',uselist=False)

	def __init__(self, **data):

		if "from_desc" in data:
			results = create_character_info(data.pop('from_desc'))
			data['name'] = results['name']
			data['handle'] = results['handle']
			data['bio'] = results['bio']
			data['instructions'] = results['prompt']
			data['male'] = results['male']

			data['image'] = create_character_image(results['img_prompt_keywords'], male=data['male'])

		super().__init__(**data)

		self.color = self.color or generate_color()
		#self.uid = self.uid or generate_uid()

	def start_direct_chat(self, session=None):
		if self.direct_chat and not self.direct_chat.archived:
			return self.direct_chat

		sess = session or ScopedSession()
		direct_chat = DirectChat()
		direct_chat.partner = self
		sess.add(direct_chat)
		sess.commit()
		return direct_chat

	def get_all_accessible_messages(self, stop_before=None):
		chats = [chat for chat in self.chats + [self.direct_chat] if chat]
		if isinstance(stop_before, Message):
			# need to convert here because the actual message might not be in the messages (different chats)
			stop_before = stop_before.timestamp
		msgs = [msg for chat in chats for msg in chat.get_messages(stop_before=stop_before, visible_to=self)]
		msgs = sorted(msgs, key=lambda x: x.timestamp)
		return msgs

	def serialize(self):
		self.start_direct_chat()
		return {
			'name': self.name,
			'handle': self.handle,
			'bio': self.bio,
			'image': self.image,
			'instructions': self.instructions,
			'friend': self.friend,
			'direct_chat': {'ref': 'chats', 'key': self.direct_chat.uid} if self.direct_chat else None
		}

	def get_prompt(self):
		return prompts.CHARACTER_INSTRUCTION_PROMPT.format(assistant=self)

	def get_relevant_knowledge_bits(self,long_term,time):
		session = ScopedSession()
		bits = session.query(KnowledgeBit).where(and_(
			KnowledgeBit.author == self,
			KnowledgeBit.long_term == long_term,
			KnowledgeBit.timestamp < time
		)).all() #for now only owned ones
		bitmap = {} # hehe
		for bit in bits:
			bitmap[bit.number] = bit
		return bitmap.values()

	def get_knowledge_bit_prompt(self,long_term,time):
		bits = self.get_relevant_knowledge_bits(long_term,time)
		if bits:
			if long_term:
				result = "ADDITIONAL INFO:"
			else:
				result = "CURRENT SITUATION:"
			for bit in bits:
				result += f"\n* [fact:{bit.number}] {bit.desc}"
			#result += "\nOnly update or remove these knowledge bits when things have significantly changed"
			return result
		else:
			return None

	def sanitized_handle(self):
		return ''.join(char for char in self.handle if char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-')


class Protagonist:
	name = config['user']['name']
	color = "blue"
	uid = 0
	handle = config['user']['handle']

	@classmethod
	def sanitized_handle(cls):
		return cls.handle


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

	uid = Column(Integer, primary_key=True)
	chat_id = Column(Integer, ForeignKey('chats.uid'))
	chat = relationship('Chat', backref='messages')
	author_handle = Column(String, ForeignKey('people.handle'))
	author = relationship('Partner', backref='messages', foreign_keys=[author_handle])
	timestamp = Column(Integer)
	message_type = Column(Enum(MessageType), default=MessageType.Text)
	content = Column(String, default="")
	content_secondary = Column(String)  # used for media description
	media_attached = Column(String)
	linked_contact_handle = Column(String, ForeignKey('people.handle'))
	linked_contact = relationship('Partner', foreign_keys=[linked_contact_handle])

	def __init__(self, **data):
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
			'author': {'ref': 'contacts', 'key': self.get_author().handle} if not self.is_from_user() else None,
			'own': (self.get_author() is Protagonist),
			'chat': {'ref': 'chats', 'key': self.chat.uid},
			'content': self.content or "",
			'linked_entity': {'ref': 'contacts', 'key': self.linked_contact.handle } if self.message_type == MessageType.Contact else None,
			'message_type': self.message_type.name if self.message_type else None,
			'timestamp': self.timestamp,
			'display_simplified': self.content and (len(self.content)<6) and ("" == emoji.replace_emoji(self.content, replace=''))
		}

	def display_for_model(self, vision=False, add_author: Partner | Protagonist | bool = None):

		if add_author is True:
			add_author = self.author
		elif add_author is False:
			add_author = None

		prefix = f"{add_author.name}: " if add_author else ""

		if self.message_type in [None, MessageType.Text]:
			return prefix + self.content
		elif (self.message_type == MessageType.Image) and vision:
			if self.content.startswith("data:"):
				encodedimg = self.content
			elif self.content.startswith("https://"):
				encodedimg = self.content
			else:
				encodedimg = image_encode_b64('.' + self.content)

			msg = [
				{
					'type': 'image_url',
					'image_url': {
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

	uid = Column(Integer, primary_key=True)
	chat_uid = Column(String, ForeignKey('chats.uid'))
	chat = relationship('Chat', backref='summaries')


class Chat(Base):
	__tablename__ = 'chats'

	uid = Column(Integer, primary_key=True)
	subtype = Column(String)
	archived = Column(Boolean, default=False)
	total_paid = Column(Integer, default=0)
	# 10 000 = 1 ct
	# 1 000 000 = 1 usd
	__mapper_args__ = {'polymorphic_on': subtype}

	def get_ai_accessible_funcs(self):
		cls = self.__class__
		fulldict = {}
		for baseclass in reversed(cls.__mro__):
			fulldict.update(baseclass.__dict__)

		funcs = [f for f in fulldict.values() if getattr(f,'_aiaccessible',False)]
		funcs = {f.__name__:{'schema':f._schema,'lazyschema':f._lazyschema,'func':f,'lazy':getattr(f,'_lazy',False),'nonterminating':getattr(f,'_nonterminating',False)} for f in funcs}
		return funcs

	@ai_accessible_function(
		prompt="Keywords that objectively describe what the image shows to someone who has no context or knowledge of you or this chat.\
			If the picture includes yourself or other chat participants, make sure the keywords describe your or their appearance to the best of your knowledge. \
			Don't just add your name, add things like your ethnicity, hair color etc.\
			You may use quite a few keywords here and go into detail.",
		prompt_fulltext="The prompt for the image, but as a continuous descriptive text.",
		negative_prompt="Keywords for undesirable traits or content of the picture.",
		selfie="Whether this is a picture of yourself.",
		short_desc="A short description of what the picture shows for visually impaired users.",
		landscape="Whether to send a picture in landscape mode instead of portrait mode"
	)
	def send_image(self, author: Partner | Protagonist, timestamp: int,
				   prompt: List[str],
				   prompt_fulltext: str = "",
				   negative_prompt: List[str] = [],
				   selfie: bool = False,
				   short_desc: str = "",
				   landscape: bool = False
	):
		"Send an image in the chat. It should be used very rarely, only when sending a picture fits the context or is requested.\
		You also cannot randomly send pictures of other people, unless context indicates that you're currently in the same loction together.\
		Do not simply send a picture just because the previous message is a picture."
		imageformat = Format.Landscape if landscape else Format.Portrait

		img = AI['ImageGeneration'].create_image(keyword_prompt=prompt, keyword_prompt_negative=negative_prompt, fulltext_prompt=prompt_fulltext, imageformat=imageformat)
		m = self.add_message(author=author,message_type=MessageType.Image,content=img,content_secondary=short_desc)
		yield m

	@ai_accessible_function(
		name="The contact's informal name - prename or nickname",
		male="True if the contact is male, false if they are female.",
		short_description="Objectively describe the contact. Include name and sex again, but also character, ethnicity, looks, etc. without any relation to the current chat context.\
			Please do not editorialize this according to your character, but write neutrally.",
		context_introduction="A summary directed at the new contact (in second person), detailing all interactions and relevant events involving them up to this point \
			(even their own actions and opinions), speaking as a neutral instructor (not yourself).",
		add_to_groupchat="Whether to add this contact to the chat instead of simply sending them. Only works in group chats."
	)
	def send_contact(self, author: Partner | Protagonist, timestamp: int,
						name: str,
						male: bool,
						short_description: str,
						context_introduction: str,
						add_to_groupchat: bool | None = False
					):
		"Send contact info of a person you know to the chat. It should only be used when a chat partner explicitly requests their contact details, not simply everytime someone mentions another person."

		session = ScopedSession()

		char = session.query(Partner).where(Partner.name == name).first()
		if not char:
			char = Partner(from_desc=short_description, introduction_context=context_introduction)
			session.add(char)
			session.commit()
		handle = char.handle

		if add_to_groupchat and isinstance(self, GroupChat):
			m = self.add_person(char)
			yield m
		else:
			m = self.add_message(author=author, message_type=MessageType.Contact, linked_contact=char)
			yield m

	@ai_accessible_function()
	@lazy
	def send_meme(self, author: Partner | Protagonist = None, timestamp: int = None, resolve=None, args={}):
		"Send a meme"

		customfuncs = memes.get_functions()
		if resolve:
			func = customfuncs[resolve]['func']
			result = func(**args)
			m = self.add_message(author=author,message_type=MessageType.Image,content=result['image'],content_secondary=result['desc'])
			return [m]
		else:
			return customfuncs

	#@ai_accessible_function
	@non_terminating
	def update_knowledge_bit(self,author,timestamp,
		short_desc: (('string',),True,"A short description of the knowledge, e.g. 'Closer relationship' or 'Vacation plans'"),
		full_desc: (('string',),True,"A concise, objective, third-person summary of the new knowledge, e.g. 'John has invited Amy, Bob and Carol to a vacation in Switzerland. They are currently planning it.'"),
		#important: (('boolean',),True,"Whether the information is so vital for you that it should always be in your context window. This should be true for significant changes in your character, situation or relationship that affect your base prompt."),
		long_term: (('boolean',),True,"Whether this is long term information (like your character or relationship having changed) or some temporary info (like what's currently happening)"),
		number: (('integer',),True,"If you update an existing knowledge bit, use its number. Otherwise use an unused number.") = None
	):
		"""Create or edit a knowledge bit. Use this function when you learn about relevant details concerning your character or relationships, AND when learning details about what you are currently doing.
		Don't constantly create new bits about things that are already in your knowledge bits.
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
			'messages': [msg.serialize() for msg in self.get_messages()],
			'cost': self.readable_cost()
		}

	def add_message(self, author: Partner | Protagonist = None, timestamp: int = None, **keys):
		if msgt := keys.pop('msgtype', None):
			keys['message_type'] = {
				'image': MessageType.Image,
				'video': MessageType.Video
			}[msgt]

		session = ScopedSession()
		m = Message(**keys)
		m.chat = self
		if author is Protagonist:
			m.author = None
		else:
			m.author = author
		m.timestamp = timestamp or now()
		session.add(m)
		session.commit()
		return m

	def get_messages(self, stop_before: Message | int = None, visible_to: Partner = None):
		msgs = sorted(self.messages, key=lambda x: x.timestamp)

		if visible_to:
			relevant_messages = []
			for msg in msgs:
				if msg.message_type == MessageType.MetaJoin and msg.author == visible_to:
					relevant_messages = []
				relevant_messages.append(msg)
			msgs = relevant_messages

		if stop_before:
			relevant_messages = []
			for msg in msgs:
				if (msg is stop_before) or (isinstance(stop_before, int) and (msg.timestamp >= stop_before)):
					break
				else:
					relevant_messages.append(msg)
			msgs = relevant_messages

		return msgs

	def send_message(self, content: str = None, msgtype: MessageType = None):
		return self.add_message(Protagonist, content=content, msgtype=msgtype)

	def get_response(self, replace: Message | int = None, responder: Partner = None):
		if not responder:
			responder = replace.author if replace else self.pick_next_responder()

		handler: AIProvider = AI['ChatResponse']

		vision_capable = handler.is_vision_capable()
		use_vision = vision_capable and any(m.message_type == MessageType.Image for m in self.get_messages()[-MAX_MESSAGES_VISION:])

		messages = list(handler.get_messages(self, partner=responder, upto=replace, images=use_vision))
		if use_vision:
			messages = messages[-MAX_MESSAGES_IN_CONTEXT_WITH_VISION:]

		try:
			result = handler.respond_chat(chat=self, messagelist=messages, responder=responder, allow_functioncall=(not replace))
		except errors.ContentPolicyError:
			messages = list(handler.get_messages(self, partner=responder, upto=replace, images=False))
			result = handler.respond_chat(chat=self, messagelist=messages, responder=responder, allow_functioncall=(not replace))

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
			yield from funccall['function'](self=self, author=responder, timestamp=replace.timestamp if replace else now(), **funccall['arguments'])

	def get_summary(self, partner: Partner, external=False, timestamp=None):

		messages = self.get_messages(stop_before=timestamp)
		result = summarize_chat(messages, perspective=partner, external=external)

		return result


class DirectChat(Chat):
	__tablename__ = 'directchats'
	uid = Column(Integer, ForeignKey('chats.uid'), primary_key=True)

	partner_handle = Column(String, ForeignKey('people.handle'))
	partner = relationship('Partner', back_populates='direct_chat', uselist=False)

	__mapper_args__ = {'polymorphic_identity': 'direct'}

	def serialize_short(self):
		return {
			'uid': self.uid,
			'partner': {'ref': 'contacts', 'key': self.partner.handle},
			'groupchat': False,
			'latest_message': self.get_messages()[-1].serialize() if self.messages else None,
			'pinned': self.partner.pinned or False
		}

	def ai_participants(self):
		return [self.partner]

	def clean_content(self, content: str, responder: Partner):
		return content

	def pick_next_responder(self):
		return self.partner


class GroupChat(Chat):
	__tablename__ = 'groupchats'
	uid = Column(Integer,ForeignKey('chats.uid'),primary_key=True)

	name = Column(String, default="New Group")
	desc = Column(String, default="")
	image = Column(String)
	pinned = Column(Boolean, default=False)

	members = relationship("Partner", secondary=chat_to_member, back_populates="chats")

	__mapper_args__ = {'polymorphic_identity': 'group'}

	def get_group_desc_prompt(self,perspective):
		memberlist = ', '.join(
			f"{'You' if p is perspective else p.name} (@{p.handle})"
			for p in self.members + [Protagonist]
		)

		return f"Group Chat Name: {self.name}\nGroup Chat Members: {memberlist}"

	def ai_participants(self):
		return self.members

	@ai_accessible_function(
		name="New name"
	)
	def rename_chat(self, author, timestamp,
						name: str
					):
		"Can be used to rename the current group chat. This should be used only when there is a specific reason, or sometimes for comedic effect."

		self.name = name
		m = self.add_message(message_type=MessageType.MetaRename, author=author, content=name)
		yield m

	@ai_accessible_function(
		prompt="Keywords that describe the image",
		prompt_fulltext="Full text description of the image",
		negative_prompt="Keywords for undesirable traits or content of the picture."
	)
	def change_group_picture(self, author: Partner | Protagonist, timestamp: int,
							 prompt: List[str],
							 prompt_fulltext: str,
							 negative_prompt: List[str] | None = []
							 ):
		"Can be used to change the group picture. This should only be used when there is a specific reason, or rarely for comedic effect."

		img = AI['ImageGeneration'].create_image(keyword_prompt=prompt, keyword_prompt_negative=negative_prompt, fulltext_prompt=prompt_fulltext, imageformat=Format.Square)
		self.image = img
		m = self.add_message(message_type=MessageType.MetaChangePicture,author=author,content=img)
		yield m

	def serialize_short(self):
		return {
			'uid': self.uid,
			'name': self.name,
			'groupchat': True,
			'desc': self.desc,
			'image': self.image,
			'partners': [{'ref': 'contacts', 'key': p.handle} for p in self.members],
			'latest_message': self.get_messages()[-1].serialize() if self.messages else None,
			'pinned': self.pinned or False
		}

	def pick_next_responder(self):

		responder = guess_next_responder(self.get_messages(), self.members, user=Protagonist)

		if not responder:
			# Fallback
			chances = {p: 100 for p in self.members}
			mentioned = set()
			for msg in self.messages[-7:]:
				for p in self.members:
					if f"@{p.handle}" in msg.content:
						# person was mentioned
						mentioned.add(p)
					elif p is msg.author:
						# person responded after mention
						mentioned.discard(p)


			for index, msg in enumerate(reversed(self.messages[-7:])):
				# last responder never responds, going further back the penalty is reduced
				if msg.author:
					chances[msg.author] *= (index / 10)
			for p in mentioned:
				chances[p] += (200 * len(chances))

			responder = random.choices(list(chances.keys()), weights=chances.values(), k=1)[0]

		return responder

	def clean_content(self, content: str, responder: Partner):
		unwanted_prefix = f"{responder.name}: "
		if content.startswith(unwanted_prefix):
			content = content[len(unwanted_prefix):]
		return content

	def add_person(self, person: Partner | Protagonist):
		if person not in self.members:
			self.members.append(person)
			m = Message(
				message_type=MessageType.MetaJoin,
				author=person,
				chat=self,
				timestamp=now()
			)
			self.messages.append(m)
			return m


class KnowledgeBit(Base):
	__tablename__ = 'knowledgebits'
	uid = Column(Integer,primary_key=True)

	number = Column(Integer,autoincrement=True)
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

		for partner in session.query(Partner).all():

			# remove contacts with no chats and no messages sharing them
			if (not partner.chats) and (not partner.direct_chat) and (not partner.messages) and (not partner.friend):
				for msg in session.query(Message).all():
					if msg.message_type == MessageType.Contact and msg.linked_contact == partner:
						print("Not deleting", partner.name, "because they are sent as a contact.")
						break
				else:
					print("Deleting", partner.name)
					session.delete(partner)

			# archive contacts when their only references are archived
			if all(chat.archived for chat in partner.chats) and ((not partner.direct_chat) or partner.direct_chat.archived) and (not partner.friend):
				for msg in session.query(Message).all():
					if msg.message_type == MessageType.Contact and msg.linked_contact == partner:
						if not msg.chat.archived:
							print("Not archiving", partner.name, "because they are sent as a contact")
							break
				else:
					print("Archiving", partner.name)
					# do nothing for now

			# chat for friends
			if partner.friend:
				partner.start_direct_chat(session=session)

		session.commit()

		# update legacy data
		for msg in  session.query(Message).all():
			if msg.media_attached:
				if msg.content:
					print("Message", msg, "contains both content and media_attached!")
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
			print('Delete', realfile)
			os.remove(realfile)

		# make sure group titles are correct
		for groupchat in session.query(GroupChat).all():
			rename_msgs = [msg for msg in groupchat.get_messages() if msg.message_type == MessageType.MetaRename]
			if rename_msgs:
				if rename_msgs[-1].content != groupchat.name:
					print("Renaming", groupchat.name, "to", rename_msgs[-1].content)
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
