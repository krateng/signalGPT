from bottle import get, post, route, delete, static_file, run, request, auth_basic


from importlib import resources
import os

from .classes import Session, Partner, Chat, GroupChat, Message, MessageType, generate_uid
from . import config


def is_auth(user,pw):
	return (user == config['authentication']['user']) and (pw == config['authentication']['password'])


def patch(path):
	return route(path, method='PATCH')


@get("/<path>")
@auth_basic(is_auth)
def index(path):
	with resources.files('signalGPT') / 'frontend' as staticfolder:
		return static_file(path, root=staticfolder)


@get("/media/<path:path>")
@auth_basic(is_auth)
def media(path):
	return static_file(path, root="./media")


@get("/api/userinfo")
@auth_basic(is_auth)
def api_get_userinfo():
	return config['user']


@get("/api/data")
@auth_basic(is_auth)
def api_get_data():
	with Session() as session:
		return {
			'chats': { chat.uid: chat.serialize_short() for chat in session.query(Chat).all() },
			'contacts': { partner.handle: partner.serialize() for partner in session.query(Partner).all() },
			'userinfo': config['user']
		}


@get("/api/contacts")
@auth_basic(is_auth)
def api_get_contacts():
	with Session() as session:
		return {
			partner.handle: partner.serialize()
			for partner in session.query(Partner).all()
		}


@get("/api/conversations")
@auth_basic(is_auth)
def api_get_conversations():
	with Session() as session:
		return {
			chat.uid: chat.serialize_short()
			for chat in session.query(Chat).all()
		}


@get("/api/chat/<uid>")
@auth_basic(is_auth)
def api_get_chat(uid):
	with Session() as session:
		return session.query(Chat).where(Chat.uid == uid).first().serialize()


@post("/api/upload_media")
@auth_basic(is_auth)
def api_upload_media():
	file = request.files.get('file')
	filedata = file.file.read()
	fileext = file.filename.split('.')[-1].lower()

	name = generate_uid() + '.' + fileext
	path = os.path.join('media', name)
	with open(path, 'wb') as fd:
		fd.write(filedata)

	return {
		'path': '/' + path
	}

@post("/api/guess_next_responder")
@auth_basic(is_auth)
def api_guess_responder():
	info = request.json
	with Session() as session:
		chat = session.query(Chat).where(Chat.uid == info['chat_id']).first()
		if isinstance(chat,GroupChat):
			if 'force_user_handle' in info:
				user = session.query(Partner).where(Partner.handle == info['force_user_handle']).first()
				if user in chat.members:
					return user.serialize()
			return chat.pick_next_responder().serialize()
		else:
			return chat.partner.serialize()

@post("/api/generate_message")
@auth_basic(is_auth)
def api_generate_message():
	info = request.json
	#model = MODEL_ADVANCED if info['bettermodel'] else MODEL_BASE
	with Session() as session:
		chat = session.query(Chat).where(Chat.uid == info['chat_id']).first()
		if 'responder_handle' in info:
			responder = session.query(Partner).where(Partner.handle==info['responder_handle']).first()
			msgs = list(chat.get_response(responder=responder))
		else:
			msgs = list(chat.get_response())
		for msg in msgs:
			session.add(msg)
		session.commit()
		return {'messages': [m.serialize() for m in msgs]}

@post("/api/send_message")
@auth_basic(is_auth)
def api_send_message():
	info = request.json
	with Session() as session:
		chat = session.query(Chat).where(Chat.uid == info['chat_id']).first()
		m = chat.send_message(content=info['content'].strip(), msgtype=info.get('messagetype'))
		# use client timestamp? or just register now?
		session.add(m)
		session.commit()
		return m.serialize()


@post("/api/send_message_media")
@auth_basic(is_auth)
def api_send_message_message():
	info = request.forms
	file = request.files.get('file')
	filedata = file.file.read()
	fileext = file.filename.split('.')[-1].lower()
	with Session() as session:
		chat = session.query(Chat).where(Chat.uid == info['chat_id']).first()
		m = chat.send_message(add_media={'extension': fileext, 'rawdata': filedata})
		session.add(m)
		session.commit()
		return m.serialize()


@post("/api/regenerate_message")
@auth_basic(is_auth)
def api_regenerate_message():
	info = request.json
	#model = MODEL_ADVANCED if info['bettermodel'] else MODEL_BASE
	with Session() as session:
		msg = session.query(Message).where(Message.uid == info['uid']).first()
		chat = msg.chat
		msgs = list(chat.get_response(replace=msg))
		session.commit()
		return msgs[0].serialize()


# CONTACT
@get("/api/contact/<handle>")
@auth_basic(is_auth)
def api_get_contact(handle):
	with Session() as session:
		print('return',handle)
		char = session.query(Partner).where(Partner.handle == handle).first()
		print('result',char)
		return char.serialize()

@post("/api/contact")
@auth_basic(is_auth)
def api_post_contact():
	info = request.json
	with Session() as session:
		char = Partner(from_desc=info['desc'])
		chat = char.start_direct_chat(session)
		session.add(char)
		session.add(chat)
		session.commit()
		return char.serialize()


@patch("/api/contact")
@auth_basic(is_auth)
def api_patch_contact():
	info = request.json
	with Session() as session:
		contact = session.query(Partner).where(Partner.handle == info.pop('handle')).first()
		dir_chat = info.pop('start_chat', False)
		contact.__init__(**info)
		if dir_chat:
			contact.start_direct_chat(session)
		session.commit()
		return contact.serialize()


# MESSAGE
@patch("/api/message")
@auth_basic(is_auth)
def api_patch_message():
	info = request.json
	with Session() as session:
		message = session.query(Message).where(Message.uid == info.pop('uid')).first()
		message.__init__(**info)
		session.commit()
		return message.serialize()


@delete("/api/message")
@auth_basic(is_auth)
def api_delete_message():
	info = request.json
	with Session() as session:
		msg = session.query(Message).where(Message.uid == info.pop('uid')).first()
		session.delete(msg)
		session.commit()


# CHAT
@post("/api/groupchat")
@auth_basic(is_auth)
def api_post_groupchat():
	info = request.json
	with Session() as session:
		c = GroupChat(**info)
		session.add(c)
		session.commit()
		return c.serialize()


@patch("/api/chat")
@auth_basic(is_auth)
def api_patch_chat():
	info = request.json
	with Session() as session:

		chat = session.query(Chat).where(Chat.uid == info.pop('uid')).first()
		if 'name' in info and info['name'] != chat.name:
			m = chat.add_message(message_type=MessageType.MetaRename,author=None,content=info['name'])
			session.add(m)
		if 'image' in info:
			m = chat.add_message(message_type=MessageType.MetaChangePicture,author=None,content=info['image'])
			session.add(m)
		chat.__init__(**info)
		session.commit()
		return chat.serialize()


@delete("/api/chat")
@auth_basic(is_auth)
def api_delete_chat():
	info = request.json
	with Session() as session:
		chat = session.query(Chat).where(Chat.uid == info.pop('uid')).first()
		for msg in chat.messages:
			session.delete(msg)
		session.delete(chat)
		session.commit()


@post("/api/add_chat_member")
@auth_basic(is_auth)
def api_add_chat_member():
	info = request.json
	with Session() as session:
		chat = session.query(Chat).where(Chat.uid == info.pop('chat_uid')).first()
		person = session.query(Partner).where(Partner.handle == info.pop('partner_handle')).first()
		chat.add_person(person)
		session.commit()
		return chat.serialize()


run(host=config['authentication']['host'],port=9090,server='waitress')
