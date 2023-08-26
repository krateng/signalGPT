import yaml
import openai
from datetime import datetime
import shutil
import os

try:
	with open('config.yml','r') as fd:
		config = yaml.load(fd,Loader=yaml.SafeLoader)
except FileNotFoundError:
	with open('config.yml','w') as fd:
		config = {
			'apikey':'0',
			'model':'gpt-3.5-turbo-16k-0613',
			'user':{
				'name':'Anon',
				'handle':'anon',
				'description':'I am mysterious and unknowable. Love waffles.',
				'preferred_emojis':'😃🪷🇰🇷'
			}
		}
		yaml.dump(config,fd)

for folder in ['media','contacts','conversations','backups']:
	os.makedirs(folder,exist_ok=True)


openai.api_key = config['apikey']


backupfile = os.path.join("backups",datetime.utcnow().strftime("%Y-%m-%d") + ".sqlite")
shutil.copyfile("database.sqlite",backupfile)
