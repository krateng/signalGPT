from bottle import get, post, static_file, run, request

from .classes import Session, Partner, Chat, create_character


@get("/<path>")
def index(path):
	return static_file(path,root="./signalGPT/frontend")

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

run(port=9090)
