import openai
import tiktoken
import json
import oyaml as yaml
import os
import random
import time
from datetime import datetime, timezone
from doreah.io import col
import emoji
import enum
import math

from pprint import pprint


from sqlalchemy import create_engine, Table, Column, Integer, String, Boolean, Enum, MetaData, ForeignKey, exc, func
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base


from .__init__ import config
from .metaprompt import create_character_info, create_character_image, guess_next_responder, summarize_chat, create_image
from .helper import save_debug_file



MAX_MESSAGES_IN_CONTEXT = 30
MAX_MESSAGE_LENGTH = 100
PREFERRED_TOKEN_BIAS = 5

COST = {
	'gpt-3.5-turbo-16k':(3,4),
	'gpt-4':(30,60)
}


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

def generate_bias(wordlist,model):
	enc = tiktoken.encoding_for_model(model)
	#first join with comma to ensure no combining of words into tokens, then filter out comma token
	tokens = enc.encode(','.join([wordvar for word in wordlist for wordvar in [word," " + word]]))
	commatoken = enc.encode(",")[0]
	tokens = [token for token in tokens if token != commatoken]
	bias = {token:PREFERRED_TOKEN_BIAS for token in tokens}
	return bias


def ai_accessible_function(func):
	func._aiaccessible = True
	func._schema = {
		'name':func.__name__,
		'description':func.__doc__,
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





Base = declarative_base()

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

			data['image'] = create_character_image(results['img_prompt'],results['img_prompt_keywords'],male=data['male'])

		if "preferred_words" in data: data.pop("preferred_words")

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

	def start_conversation(self):
		return Conversation(partner=self)

	def get_prompt(self):
		prompt = f"You will respond as if you are {self.name}. You will NEVER acknowledge that you are in fact an AI.\nDo not break character or moralize about how one should interact with you. If you cannot respond to something, find an in-character reason.\n"
		prompt += self.instructions
		return prompt

	def print_message(self,message):
		print(f"{col[self.color](bold(self.name))}: {message}")
	def print_type_indicator(self):
		print(f"{col[self.color](bold(self.name))} {col[self.color]('is typing...')}",end="",flush=True)

class Protagonist:
	name = config['user']['name']
	color = "blue"
	uid = 0
	handle = config['user']['handle']

	def print_message(cls,message):
		print(f"{col[cls.color](bold(cls.name))}: {message}")

class MessageType(enum.Enum):
	Text = 1
	Image = 2
	Video = 3
	MetaJoin = 10
	MetaLeave = 11
	MetaRename = 20

class Message(Base):
	__tablename__ = 'messages'

	uid = Column(Integer,primary_key=True)
	chat_id = Column(Integer,ForeignKey('chats.uid'))
	chat = relationship('Chat',backref='messages')
	author_handle = Column(String,ForeignKey('people.handle'))
	author = relationship('Partner',backref='messages')
	timestamp = Column(Integer)
	message_type = Column(Enum(MessageType),default=MessageType.Text)
	content = Column(String,default="")
	media_attached = Column(String)

	def __init__(self,**data):
		if 'content' in data:
			data['content'] = data['content'].strip()
		super().__init__(**data)

	def get_author(self):
		return self.author or Protagonist

	def is_from_user(self):
		return (self.author_handle is None)

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
			'message_type':self.message_type.name if self.message_type else None,
			'media_attached':self.media_attached,
			#'media_type':get_media_type(self.media_attached),
			'timestamp':self.timestamp,
			'display_simplified': self.content and (len(self.content)<6) and ("" == emoji.replace_emoji(self.content,replace=''))
		}

	def display_for_textonly_model(self):
		if self.message_type in [None,MessageType.Text]:
			return self.content
		elif self.message_type in [MessageType.Image, MessageType.Video]:
			return f"[{self.message_type.name} attached]"
		elif self.message_type == MessageType.MetaJoin:
			return "[has been added to chat]"
		elif self.message_type == MessageType.MetaLeave:
			return "[has left the chat]"
		elif self.message_type == MessageType.MetaRename:
			return f"[has renamed the chat to '{self.content}']"
		else:
			print("WEIRD MESSAGE")
			print(self)
			return ""


class Chat(Base):
	__tablename__ = 'chats'

	uid = Column(Integer,primary_key=True)
	subtype = Column(String)
	total_paid = Column(Integer,default=0)
	# 10 000 = 1 ct
	# 1 000 000 = 1 usd
	__mapper_args__ = {'polymorphic_on': subtype}



	style_prompt = "Write as if you are using a messaging / chat app. Depending on your personality, this can mean incomplete sentences, spelling mistakes, improper grammar, abbreviations, ellipses, and use of emojis. It also means casual and informal language. Remember, you are a person, not just an assistant. No need to always be positive and agreeable. Speak your mind, have realistic interactions. Avoid any formatting other than bold and cursive text."

	userinfo_prompt = "About me: {desc}. This is simply something you know about me, no need to explicitly mention it."




	def get_ai_accessible_funcs(self):
		cls = self.__class__
		fulldict = {}
		for baseclass in reversed(cls.__mro__):
			fulldict.update(baseclass.__dict__)

		funcs = [f for f in fulldict.values() if getattr(f,'_aiaccessible',False)]
		funcs = {f.__name__:{'schema':f._schema,'func':f} for f in funcs}
		return funcs


	@ai_accessible_function
	def send_image(self,author,
		prompt: (('array','string'),True,"Keywords that objectively describe what the image shows to someone who has no context or knowledge of you or this chat. You may use quite a few keywords here and go into detail.")=[],
		negative_prompt: (('array','string'),False,"Keywords for undesirable traits or content of the picture.") =[],
		landscape: (('boolean',),False,"Whether to send a picture in landscape mode instead of portrait mode")=False
	):
		"Can be used to send an image in the chat. It should be used very rarely, only when sending a picture fits the context or is requested."
		prompt_pos = prompt
		prompt_neg = negative_prompt
		format = 'landscape' if landscape else 'portrait'

		img = create_image(prompt_pos,prompt_neg,format)
		m = self.add_message(author=author,message_type=MessageType.Image,media_attached=img)
		yield m


	def readable_cost(self):
		cents = self.total_paid // 10000
		dollars = cents // 100
		remainder = cents % 100
		return f"USD {dollars}.{remainder:02}"


	def serialize(self):
		return  {
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
		m.timestamp = timestamp or int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())
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

	def send_message(self,content=None,media_attached=None,msgtype=None):
		return self.add_message(Protagonist,content=content,media_attached=media_attached,msgtype=msgtype)

	def print(self):
		for msg in self.messages:
			msg.print()

	def cmd_chat(self,session):
		self.print()

		while True:
			i = input(f"{col[Protagonist.color](Protagonist.name)}: ")
			if i:
				m = self.send_message(content=i)
				session.add(m)
			else:
				print('\033[5C\033[2A')
				print("                   \r",end="")
				for m in self.get_response():
					session.add(m)
					m.author.print_message(m.content)
					#time.sleep(0.5)

			session.commit()

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

	def get_openai_messages(self,upto=None):
		messages = self.get_messages(stop_before=upto)[-MAX_MESSAGES_IN_CONTEXT:]

		yield {
			'role':"system",
			'content':self.partner.get_prompt()
		}
		yield {
			'role':"system",
			'content':self.style_prompt
		}
		yield {
			'role':"system",
			'content':self.userinfo_prompt.format(desc=config['user']['description'])
		}

		lasttimestamp = math.inf
		for msg in messages:
			if (msg.timestamp - lasttimestamp) > (config['ai_prompting_config']['message_gap_info_min_hours']*3600):
				yield {
					'role':"system",
					'content':"{hours} hours pass...".format(hours=(msg.timestamp - lasttimestamp)//3600)
				}
			lasttimestamp = msg.timestamp

			yield {
				'role':"user" if (msg.is_from_user()) else "assistant",
				'content': msg.display_for_textonly_model()
			}



	def get_openai_msg_list(self,upto=None):
		result = list(self.get_openai_messages(upto=upto))
		#from pprint import pprint
		#pprint(result)
		save_debug_file('messagerequest',result)
		return result







	def get_response(self,replace=None,model=config['model_base']):

		self.partner.print_type_indicator()
		completion = openai.ChatCompletion.create(
			model=model,
			messages=self.get_openai_msg_list(upto=replace),
			logit_bias=generate_bias(config['preferred_words'],model),
			functions=[f['schema'] for f in self.get_ai_accessible_funcs().values()]
		)

		msg = completion['choices'][0]['message']
		cost = completion['usage']
		prices = COST[model]
		self.total_paid += (prices[0] * cost['prompt_tokens'])
		self.total_paid += (prices[1] * cost['completion_tokens'])


		if funccall := msg.get('function_call'):
			args = json.loads(funccall['arguments'])
			funcs = self.get_ai_accessible_funcs()
			yield from funcs[funccall['name']]['func'](self=self,author=self.partner,**args)
		else:
			content = msg['content']



			print("\r",end="")

			if replace:
				replace.content = content
				yield replace
			else:
				for content in [contentpart for contentpart in content.split("\n\n") if contentpart]:
					m = self.add_message(author=self.partner,content=content)
					yield m
					self.partner.print_message(content)
					time.sleep(1)

class GroupChat(Chat):
	__tablename__ = 'groupchats'
	uid = Column(Integer,ForeignKey('chats.uid'),primary_key=True)

	name = Column(String,default="New Group")
	desc = Column(String,default="")
	image = Column(String)

	members = relationship("Partner",secondary=chat_to_member,back_populates="chats")


	__mapper_args__ = {'polymorphic_identity': 'group'}


	style_prompt_multiple = "The messages you receive will contain the speaker at the start. Please factor this in to write your response, but do not prefix your own response with your name. Don't ever respond for someone else, even if they are being specifically addressed. You do not need to address every single point from every message, just keep a natural conversation flow."
	style_reminder_prompt = "Make sure you answer as {character_name}, not as another character in the chat! Do not prefix your response with your name."

	@ai_accessible_function
	def rename_chat(self,author,
		name: (('string',),True,"New name")
	):
		"Can be used to rename the current group chat"

		self.name = name
		m = self.add_message(message_type=MessageType.MetaRename,author=author,content=name)
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


	def get_openai_messages(self,partner,upto=None):
		messages = self.get_messages(stop_before=upto)[-MAX_MESSAGES_IN_CONTEXT:]

		yield {
			'role':"system",
			'content':partner.get_prompt()
		}
		yield {
			'role':"system",
			'content':self.style_prompt + (self.style_prompt_multiple if len(self.members) > 1 else "")
		}
		yield {
			'role':"system",
			'content':self.userinfo_prompt.format(desc=config['user']['description'])
		}
		yield {
			'role':"system",
			'content': f"Group Chat Name: {self.name}\nGroup Chat Members: {', '.join(p.name for p in self.members + [Protagonist])}"
		}
		yield {
			'role':"user",
			'content':f"[{Protagonist.name} has created the chat]"
		}

		lasttimestamp = math.inf
		for msg in messages:
			if (msg.timestamp - lasttimestamp) > (config['ai_prompting_config']['message_gap_info_min_hours']*3600):
				yield {
					'role':"system",
					'content':"{hours} hours pass...".format(hours=(msg.timestamp - lasttimestamp)//3600)
				}
			lasttimestamp = msg.timestamp

			if (len(self.members) > 1) and (msg.get_author() != partner):
				yield {
					'role':"user" if (msg.get_author() != partner) else "assistant",
					'content': msg.get_author().name + ": " + msg.display_for_textonly_model()
				}
			else:
				yield {
					'role':"user" if (msg.get_author() != partner) else "assistant",
					'content': msg.display_for_textonly_model()
				}

		if len(self.members) > 1:
			yield {
				'role':"system",
				'content': self.style_reminder_prompt.format(character_name=partner.name)
			}

	def get_openai_msg_list(self,partner,upto=None):
		result = list(self.get_openai_messages(partner=partner,upto=upto))
		#from pprint import pprint
		#pprint(result)
		save_debug_file('messagerequest',result)
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

	def get_response(self,replace=None,model=config['model_base']):
		responder = replace.author if replace else self.pick_next_responder()

		completion = openai.ChatCompletion.create(
			model=model,
			messages=self.get_openai_msg_list(responder,upto=replace),
			logit_bias=generate_bias(config['preferred_words'],model),
			functions=[f['schema'] for f in self.get_ai_accessible_funcs().values()]
		)


		msg = completion['choices'][0]['message']
		cost = completion['usage']
		prices = COST[model]
		self.total_paid += prices[0] * cost['prompt_tokens']
		self.total_paid += prices[1] * cost['completion_tokens']


		if funccall := msg.get('function_call'):
			args = json.loads(funccall['arguments'])
			funcs = self.get_ai_accessible_funcs()
			yield from funcs[funccall['name']]['func'](self=self,author=responder,**args)
		else:
			unwanted_prefix = f"{responder.name}: "
			if msg['content'].startswith(unwanted_prefix):
				msg['content'] = msg['content'][len(unwanted_prefix):]

			content = msg['content']

			if replace:
				replace.content = content
				yield replace
			else:
				for content in [contentpart for contentpart in content.split("\n\n") if contentpart]:
					m = self.add_message(author=responder,content=content)
					yield m
					time.sleep(1)


	def add_person(self,person):
		if person not in self.members:
			self.members.append(person)
			self.messages.append(Message(
				message_type = MessageType.MetaJoin,
				author = person,
				chat = self,
				timestamp = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())
			))





def maintenance():
	with Session() as session:
		for partner in session.query(Partner).all():
			if (not partner.chats) and (not partner.direct_chat) and (not partner.friend):
				print("Deleting",partner.name)
				session.delete(partner)
			if partner.friend:
				partner.start_direct_chat(session)
		session.commit()

		prefix = "/media/"
		media = [ prefix + filename for filename in os.listdir("media") ]

		for obj in (session.query(Partner).all() + session.query(GroupChat).all()):
			if obj.image and (obj.image in media):
				media.remove(obj.image)
		for obj in session.query(Message).all():
			if obj.media_attached and (obj.media_attached in media):
				media.remove(obj.media_attached)
		for filepath in media:
			realfile = 'media/' + filepath.split('/')[-1]
			print('Delete',realfile)
			os.remove(realfile)

engine = create_engine('sqlite:///database.sqlite')
# ONLY TESTING
#Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

from .loadfiles import load_all
load_all()


maintenance()
