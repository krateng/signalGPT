from bottle import get, post, route, delete, static_file, run, request
patch = lambda path: route(path,method='PATCH')
from importlib import resources

from .classes import Session, Partner, Chat, Message


@get("/<path>")
def index(path):
	with resources.files('signalGPT') / 'frontend' as staticfolder:
		return static_file(path,root=staticfolder)

@get("/media/<path:path>")
def media(path):
	return static_file(path,root="./media")

@get("/api/userinfo")
def api_get_userinfo():

	from . import config
	return config['user']

@get("/api/contacts")
def api_get_contacts():
	with Session() as session:
		return {
			partner.handle: partner.serialize()
			for partner in session.query(Partner).all()
		}

@get("/api/conversations")
def api_get_conversations():
	with Session() as session:
		return {
			chat.uid: chat.serialize_short()
			for chat in session.query(Chat).all()
		}

@get("/api/chat/<uid>")
def api_get_chat(uid):
	with Session() as session:
		return session.query(Chat).where(Chat.uid==uid).first().serialize()

@get("/api/get_message/<uid>")
def api_get_message(uid):
	with Session() as session:
		chat = session.query(Chat).where(Chat.uid==uid).first()
		msgs = list(chat.get_response())
		for msg in msgs:
			session.add(msg)
		session.commit()
		return {'messages':[m.serialize() for m in msgs]}


@post("/api/send_message")
def api_send_message():
	info = request.json
	with Session() as session:
		chat = session.query(Chat).where(Chat.uid==info['chat_id']).first()
		m = chat.send_message(content=info['content'].strip())
		# use client timestamp? or just register now?
		session.add(m)
		session.commit()
		return m.serialize()

@post("/api/send_message_media")
def api_send_message_message():
	info = request.forms
	file = request.files.get('file')
	filedata = file.file.read()
	fileext = file.filename.split('.')[-1].lower()
	with Session() as session:
		chat = session.query(Chat).where(Chat.uid==info['chat_id']).first()
		m = chat.send_message(add_media={'extension':fileext,'rawdata':filedata})
		session.add(m)
		session.commit()
		return m.serialize()


@post("/api/regenerate_message")
def api_regenerate_message():
	info = request.json
	with Session() as session:
		msg = session.query(Message).where(Message.uid==info['uid']).first()
		chat = msg.chat
		msgs = list(chat.get_response(replace=msg))
		session.commit()
		return msgs[0].serialize()

@post("/api/contact")
def api_post_contact():
	info = request.json
	with Session() as session:
		char = Partner(from_desc=info['desc'])
		chat = char.start_direct_chat()
		session.add(char)
		session.add(chat)
		session.commit()
		return {
			'character':char.serialize(),
			'chat':chat.serialize()
		}

@patch("/api/contact")
def api_patch_contact():
	info = request.json
	with Session() as session:
		contact = session.query(Partner).where(Partner.handle==info.pop('handle')).first()
		contact.__init__(**info)
		session.commit()
		return contact.serialize()

@patch("/api/message")
def api_patch_message():
	info = request.json
	with Session() as session:
		message = session.query(Message).where(Message.uid==info.pop('uid')).first()
		message.__init__(**info)
		session.commit()
		return message.serialize()

@delete("/api/message")
def api_delete_message():
	info = request.json
	with Session() as session:
		msg = session.query(Message).where(Message.uid==info.pop('uid')).first()
		session.delete(msg)
		session.commit()

@post("/api/delete_chat")
def api_delete_chat():
	info = request.json
	with Session() as session:
		chat = session.query(Chat).where(Chat.uid==info['uid']).first()
		for msg in chat.messages:
			session.delete(msg)
		session.delete(chat)
		session.commit()


run(port=9090)
