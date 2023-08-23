from bottle import get, post, static_file, run, request
from importlib import resources

from .classes import Session, Partner, Chat, Message, create_character


@get("/<path>")
def index(path):
	with resources.files('signalGPT') / 'frontend' as staticfolder:
		return static_file(path,root=staticfolder)

@get("/media/<path:path>")
def media(path):
	return static_file(path,root="./media")

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
		m = chat.send_message(info['content'])
		# use client timestamp? or just register now?
		session.add(m)
		session.commit()
@post("/api/regenerate_message")
def api_regenerate_message():
	info = request.json
	with Session() as session:
		msg = session.query(Message).where(Message.uid==info['uid']).first()
		chat = msg.chat
		msgs = list(chat.get_response(replace=msg))
		return {'content':msgs[0].content}

@post("/api/find_contact")
def api_find_contact():
	info = request.json
	with Session() as session:
		char = create_character(info['searchstr'])
		chat = char.start_direct_chat()
		session.add(char)
		session.add(chat)
		session.commit()
		return {
			'character':char.serialize(),
			'chat':chat.serialize()
		}

@post("/api/add_friend")
def api_add_friend():
	info = request.json
	with Session() as session:
		char = session.query(Partner).where(Partner.handle==info['handle']).first()
		char.friend = True
		session.commit()

@post("/api/edit_message")
def api_edit_message():
	info = request.json
	with Session() as session:
		msg = session.query(Message).where(Message.uid==info['uid']).first()
		msg.content = info['content']
		session.commit()

@post("/api/delete_message")
def api_delete_message():
	info = request.json
	with Session() as session:
		msg = session.query(Message).where(Message.uid==info['uid']).first()
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
