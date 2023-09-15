import yaml
import openai
from datetime import datetime
import shutil
import os

try:
	with open('config.yml', 'r') as fd:
		config = yaml.load(fd, Loader=yaml.SafeLoader)
except FileNotFoundError:
	with open('config.yml', 'w') as fd:
		config = {
			'apikey': None,
			'model_base': 'gpt-3.5-turbo-16k', # MUCH cheaper
			'model_advanced': 'gpt-4', # very useful for good character consistency and individuality
			'model_meta': 'gpt-4', #pretty much necessary for next responder prediction, gpt-3 doesn't understand how group chats work
			'user': {
				'name': 'Anon',
				'handle': 'anon',
				'description': 'I am mysterious and unknowable. Love waffles.',
				'preferred_emojis': '😃🪷🇰🇷'
			},
			'auth': {
				'anydream': {
					'import': False
				}
			}
		}
		yaml.dump(config, fd)

for folder in ['media', 'contacts', 'conversations', 'backups','debug']:
	os.makedirs(folder, exist_ok=True)

openai.api_key = config['apikey']

if os.path.exists("database.sqlite"):
	backupfile = os.path.join("backups", datetime.utcnow().strftime("%Y-%m-%d") + ".sqlite")
	shutil.copyfile("database.sqlite", backupfile)
