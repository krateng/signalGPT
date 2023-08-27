import openai
import json
import oyaml as yaml
import os
import random
import time
from datetime import datetime, timezone
from doreah.io import col
import emoji


from sqlalchemy import create_engine, Table, Column, Integer, String, Boolean, MetaData, ForeignKey, exc, func
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base


from .__init__ import config
from .metaprompt import create_character_info, create_character_image



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
		if ext in ['mp4','mkv','webm','avi']: return 'video'
		if ext in ['jpg','jpeg','png','gif','webp']: return 'image'


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

			data['image'] = create_character_image(results['img_prompt'],results['img_prompt_keywords'])

		super().__init__(**data)

		self.color = self.color or generate_color()
		#self.uid = self.uid or generate_uid()
		if self.friend:
			self.start_direct_chat()


	def start_direct_chat(self):
		if self.direct_chat:
			return self.direct_chat

		direct_chat = DirectChat()
		direct_chat.partner = self
		return direct_chat

	def serialize(self):
		return {
			'name':self.name,
			'handle':self.handle,
			'bio':self.bio,
			'uid':self.uid,
			'image':self.image,
			'instructions':self.instructions,
			'friend':self.friend
		}
	def add_contact(self):
		self.permanent = True
		with open(os.path.join("partners",self.handle + ".json"),"w") as fd:
			json.dump(self.serialize(),fd,indent=4)

	def start_conversation(self):
		return Conversation(partner=self)

	def get_prompt(self):
		prompt = f"You will respond as if you are {self.name}. You will NEVER acknowledge that you are in fact an AI.\nDo not break character or moralize about how one should interact with you. If you cannot respond to something, find an in-character reason."
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

	def print_message(self,message):
		print(f"{col[self.color](bold(self.name))}: {message}")


class Message(Base):
	__tablename__ = 'messages'

	user = Column(Boolean,default=False)
	uid = Column(Integer,primary_key=True)
	chat_id = Column(Integer,ForeignKey('chats.uid'))
	chat = relationship('Chat',backref='messages')
	author_handle = Column(String,ForeignKey('people.handle'))
	author = relationship('Partner',backref='messages')
	timestamp = Column(Integer)
	content = Column(String,default="")
	media_attached = Column(String)

	def __init__(self,**data):
		if 'content' in data:
			data['content'] = data['content'].strip()
		super().__init__(**data)

	def get_author(self):
		if self.user:
			return Protagonist()
		else:
			return self.author

	def print(self):
		self.get_author().print_message(self.content)


	def serialize(self):
		return {
			'uid': self.uid,
			'author':self.get_author().handle,
			'own':self.user,
			'content':self.content or "",
			'media_attached':self.media_attached,
			'media_type':get_media_type(self.media_attached),
			'timestamp':self.timestamp,
			'display_simplified': self.content and (len(self.content)<6) and ("" == emoji.replace_emoji(self.content,replace=''))
		}

	def display_for_textonly_model(self):
		txt = self.content or ""
		if self.media_attached:
			txt += " [Media attached]"
		return txt


class Chat(Base):
	__tablename__ = 'chats'

	uid = Column(Integer,primary_key=True)
	subtype = Column(String)

	__mapper_args__ = {'polymorphic_on': subtype}



	style_prompt = "Write as if you are using a messaging / chat app. Depending on your personality, this can mean incomplete sentences, spelling mistakes, improper grammar, abbreviations, ellipses, and use of emojis. It also means casual and informal language. Remember, you are a person, not just an assistant. No need to always be positive and agreeable. Speak your mind, have realistic interactions. Avoid any formatting other than bold and cursive text."

	userinfo_prompt = "About me: {desc}. This is simply something you know about me, no need to explicitly mention it."


	def serialize(self):
		return  {
			**self.serialize_short(),
			'messages':[msg.serialize() for msg in self.get_messages()]
		}


	def add_message(self,author,content="",timestamp=None,media_attached=None):
		m = Message()
		m.chat = self
		if author is Protagonist:
			m.user = True
		else:
			m.author = author
		m.content = content
		m.timestamp = timestamp or int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())
		m.media_attached = media_attached
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

	def send_message(self,content=None,media_attached=None):
		return self.add_message(Protagonist,content=content,media_attached=media_attached)

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

	def get_summary(self,partner,timestamp):
		completion = openai.ChatCompletion.create(model=config['model'],messages=[
			{
				'role':'user',
				'content':msg.get_author().name + ": " + msg.display_for_textonly_model()
			}
			for msg in self.get_messages(stop_before=timestamp)
		] + [
			{
				'role':'user',
				'content':f'''Please analzye the above chat and what happened during it for the character {partner.name}.
					Summarize important implications in terms of character development or changes in relationship dynamics.
					Do not include every single thing that happened. Do not describe all steps that lead to it, only the final outcomes.
					Write your summary in the form of information bits for a chatbot who is supposed to act as {partner.name} and needs to be updated on their knowledge, behavious, character, relationships etc. based on this chat.
					Do not add any meta information. Speak in second person to the chatbot {partner.name}. Speak as if you are {Protagonist.name} (first person).
					Do not give any general chatbot instructions, only tell them what new information they need to know based on this chat.
					Do not give advice or instructions. Simpy inform about relevant changes.
					Do not refer to this chat or how you learned these things. Simply inform the chatbot that these things happened in the meantime.
					Be very concise. Bullet points like "Your relationship with X has become more intimate", "You visited Japan with X" or "X has invited you to a football game" are sufficent.'''
			}
		])
		msg = completion['choices'][0]['message']
		content = msg['content']
		return content


class DirectChat(Chat):
	__tablename__ = 'directchats'
	uid = Column(Integer,ForeignKey('chats.uid'),primary_key=True)

	partner_handle = Column(String,ForeignKey('people.handle'))
	partner = relationship('Partner',back_populates='direct_chat',uselist=False)

	__mapper_args__ = {'polymorphic_identity': 'direct'}



	def serialize_short(self):
		return {
			'uid':self.uid,
			'partner':self.partner_handle,
			'name':self.partner.name,
			'groupchat':False,
			'desc':self.partner.bio,
			'image':self.partner.image,
			'latest_message':self.get_messages()[-1].serialize() if self.messages else None
		}

	def get_openai_msg_list(self,upto=None):
		messages = self.get_messages_upto(upto)

		return [
			{
				'role':"system",
				'content':self.partner.get_prompt()
			},
			{
				'role':"system",
				'content':self.style_prompt
			},
			{
				'role':"system",
				'content':self.userinfo_prompt.format(desc=config['user']['description'])
			}
		] + [
			{
				'role':"user" if (msg.user) else "assistant",
				'content': msg.display_for_textonly_model()
			}
			for msg in messages
		]



	def get_response(self,replace=None):
		self.partner.print_type_indicator()
		completion = openai.ChatCompletion.create(model=config['model'],messages=self.get_openai_msg_list(upto=replace))
		msg = completion['choices'][0]['message']
		content = msg['content']

		print("\r",end="")

		if replace:
			replace.content = content
			yield replace
		else:
			for content in [contentpart for contentpart in content.split("\n\n") if contentpart]:
				m = self.add_message(self.partner,content)
				yield m
				self.partner.print_message(content)
				#time.sleep(0.5)

class GroupChat(Chat):
	__tablename__ = 'groupchats'
	uid = Column(Integer,ForeignKey('chats.uid'),primary_key=True)

	name = Column(String,default="New Group")
	desc = Column(String,default="")
	image = Column(String)

	members = relationship("Partner",secondary=chat_to_member,back_populates="chats")


	__mapper_args__ = {'polymorphic_identity': 'group'}


	style_prompt_multiple = "The messages you receive will contain the speaker at the start. Please factor this in to write your response, but do not prefix your own response with your name. Don't ever respond for someone else, even if they are being specifically addressed. You do not need to address every single point from every message, just keep a natural conversation flow."
	style_reminder_prompt = "Make sure you answer as {character_name}, not as another character in the chat!!!"



	def serialize_short(self):
		return {
			'uid':self.uid,
			'name':self.name,
			'groupchat':True,
			'desc':self.desc,
			'image':self.image,
			'partners':{p.handle:p.name for p in self.members},
			'latest_message':self.get_messages()[-1].serialize() if self.messages else None
		}



	def get_openai_msg_list(self,partner,upto=None):
		messages = self.get_messages_upto(upto)

		return [
			{
				'role':"system",
				'content':partner.get_prompt()
			},
			{
				'role':"system",
				'content':self.style_prompt + (self.style_prompt_multiple if len(self.members) > 1 else "")
			},
			{
				'role':"system",
				'content':self.userinfo_prompt.format(desc=config['user']['description'])
			}
		] + [
			{
				'role':"user" if (msg.get_author() != partner) else "assistant",
				'content': (msg.get_author().name + ": " + msg.display_for_textonly_model()) if ((msg.get_author() != partner) and len(self.members) > 1) else msg.display_for_textonly_model()
			}
			for msg in messages
		] + ([
			{
				'role':"system",
				'content': self.style_reminder_prompt.format(character_name=partner.name)
			}
		] if len(self.members) > 1 else [])


	def pick_next_responder(self):
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

	def get_response(self,replace=None):
		responder = replace.author if replace else self.pick_next_responder()


		#responder.print_type_indicator()

		completion = openai.ChatCompletion.create(model=config['model'],messages=self.get_openai_msg_list(responder,upto=replace))
		msg = completion['choices'][0]['message']
		unwanted_prefix = f"{responder.name}: "
		if msg['content'].startswith(unwanted_prefix):
			msg['content'] = msg['content'][len(unwanted_prefix):]

		content = msg['content']

		if replace:
			replace.content = content
			yield replace
		else:
			for content in [contentpart for contentpart in content.split("\n\n") if contentpart]:
				m = self.add_message(responder,content)
				yield m


	def add_person(self,person):
		self.members.append(person)





def maintenance():
	with Session() as session:
		for partner in session.query(Partner).all():
			if (not partner.chats) and (not partner.direct_chat) and (not partner.friend):
				print("Deleting",partner.name)
				session.delete(partner)
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
