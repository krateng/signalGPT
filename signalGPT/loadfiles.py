import sys
import os
import yaml
import json

from .classes import Session, Partner, Protagonist, Message, GroupChat, DirectChat


def load_all():

	for f in os.listdir("./contacts"):
		if f.split('.')[-1].lower() in ['yaml','yml']:
			with open(os.path.join("./contacts",f),'r') as fd:
				data = yaml.load(fd,Loader=yaml.SafeLoader)

			load_contact(data)


	for f in os.listdir("./conversations"):
		if f.split('.')[-1].lower() in ['yaml','yml']:
			with open(os.path.join("./conversations",f),'r') as fd:
				data = yaml.load(fd,Loader=yaml.SafeLoader)

			load_conversation(data)




def load_conversation(data):

	if "partner" in data:
		load_direct_conversation(data)
	elif "members" in data:
		load_group_conversation(data)
	else:
		print("Could not load conversation.")

def load_direct_conversation(data):
	with Session() as session:
		p = session.query(Partner).where(Partner.handle==data['partner']).first()
		chat = p.start_direct_chat(session)
		#session.add(chat)

		for msg in data['messages']:
			if not msg.get('discard',False):
				ts = msg.get('timestamp_modified') or msg.get('timestamp')
				m = session.query(Message).where(Message.timestamp==ts and Message.chat==chat).first()
				if m:
					m.__init__(
						content=msg['content'],
						author=p if not msg['user'] else None
					)
				else:
					m = Message(
						timestamp=ts,
						chat=chat,
						content=msg['content'],
						author=p if not msg['user'] else None
					)
					session.add(m)
		session.commit()

def load_group_conversation(data):

	if data.get('image') and data['image'].startswith("./"):
		data['image'] = "/media/" + data['image'].split("./",1)[1]

	members = data.pop('members',[])
	with Session() as session:
		select = session.query(GroupChat).where(GroupChat.name == data['name'])
		c = session.scalars(select).first()
		if c:
			c.__init__(**data)
			# change data
		else:
			c = GroupChat(**data)

		for handle in members:
			c.add_person(session.query(Partner).where(Partner.handle==handle).first())

		session.add(c)
		session.commit()

def load_contact(data):

	data['user_defined'] = True
	#data['friend'] = True

	if data.get('image') and data['image'].startswith("./"):
		data['image'] = "/media/" + data['image'].split("./",1)[1]

	with Session() as session:
		select = session.query(Partner).where(Partner.handle == data['handle'])
		p = session.scalars(select).first()
		if p:

			if data.get('dismiss',False):
				if p.direct_chat:
					session.delete(p.direct_chat)
				session.delete(p)
			else:
				p.__init__(**data)
			# change data
		else:
			if not data.get('dismiss',False):
				p = Partner(**data)
				session.add(p)


		session.commit()
