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
			'ai_prompting_config': {
				'chat_summary_update_min_hours': 96,
			    'chat_summary_update_min_messages': 30,
			    'message_gap_info_min_hours': 1
			},
			'use_service':{
				'ChatResponse': 'openai',
				'ImageGeneration': 'anydream'
			},
			'user': {
				'name': 'Anon',
				'handle': 'anon',
				'description': 'I am mysterious and unknowable. Love waffles.',
				'preferred_emojis': '😃😄😆😅😂😊😇😍🤯🤔🔥🇰🇷🇨🇭',
				'utc_offset': 0
			},
			'service_config': {
				'anydream': {
					'import': False
				},
				'openai':{
					'apikey': None,
					'model': 'gpt-4',
					'model_meta': 'gpt-4-1106-preview'
				}
			},
			'authentication': {
				'username': 'anon',
				'password': 'password',
				'host': '0.0.0.0'
			}
		}
		yaml.dump(config, fd)

for folder in ['media', 'contacts', 'conversations', 'backups','debug']:
	os.makedirs(folder, exist_ok=True)

if os.path.exists("database.sqlite"):
	backupfile = os.path.join("backups", datetime.utcnow().strftime("%Y-%m-%d") + ".sqlite")
	shutil.copyfile("database.sqlite", backupfile)
