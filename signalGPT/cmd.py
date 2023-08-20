from .classes import GroupChat, Chat, Protagonist, Partner, create_character, Session
from sqlalchemy import select
from sqlalchemy.sql.expression import func

from doreah.io import col


new = False


if new:
	with Session() as session:
		chars = []
		while True:
			prompt = input("New character: ")
			if prompt:
				c = create_character(prompt)
				chars.append(c)
				session.add(c)
			else:
				break
				
		session.commit()
		if len(chars) > 1:
			c = GroupChat(members=chars)
		else:
			c = chars[0].direct_chat
		
		
		c.cmd_chat(session)	
else:
	with Session() as session:

		chat = session.query(Chat).order_by(func.random()).first()
		if chat:
			gc = chat
		else:
			gc = GroupChat(members=[miyo])
			session.add(gc)
			session.commit()
			# start new


		gc.cmd_chat(session)









